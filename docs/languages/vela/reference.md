# Vela language reference

This reference gives each Vela construct's syntax, meaning, a short example and
its implementation status. It covers the
[first supported release](first-release.md#release-boundary) and lists the
[extension designs](extensions/README.md) only as parsed or designed syntax.
The linked owners decide meaning: [primitive semantics](first-release.md#primitive-semantics),
[module rules](first-release.md#modules-and-packages),
[ownership libraries](first-release.md#ownership-libraries),
[core loan and refinement rules](core-design.md) and the
[development surface grammar](surface-grammar.md). Where this page summarizes a
rule, the owner wins. The [primary design](verification-strategy.md) supplies the
rationale and longer examples.

## How to read this reference

Each construct carries one implementation-status marker, derived from the
prototype contracts:

| Marker | Status | Owner |
| --- | --- | --- |
| **P** | Checked by the pure prototype and emitted as Gallina over `Nat` and `bool` | [Pure prototype](vela-prototype.md#source-fragment) |
| **M** | Accepted by the opt-in mathematical elaborator, which emits CIC terms for kernel replay | [Mathematical elaborator](elaboration-prototype.md#supported-mathematical-increment) |
| **S** | Parsed as located syntax by the development parser, with no semantic consumer | [Surface grammar](surface-grammar.md#required-syntax) |
| **D** | Specified by a design contract, not yet parsed in the spelling shown | The linked contract |

P implies M unless the row says otherwise, and M implies S. No marker is a
release implementation: represented semantics, checked source correspondence,
lowering and production qualification belong to the first-release delivery
plan. An M marker records that the elaborator accepts and emits a construct as
its real kernel proposition; obligations discharged by the Python solver are
emitted and audited in the explicit solver-trust ledger rather than accepted as
closed ([Q25af](../../../PLAN.md#q-assessment-actions)).

Both parser routes enforce the settled surface spellings
([Q25ah](../../../PLAN.md#q-assessment-actions)):
`open (...) lifts ...` for invariant lifting, `let` or `var` on every local,
bare nullary constructors, `Pattern => body,` arms in every match and `restores`
with its returned-loan meaning.

Examples labeled **parsed** are accepted by
`python tools/run.py vela-parser parse --surface FILE` at this document's
revision; examples labeled **design** show the intended surface where a feature
exceeds the implemented parser or elaborator subset.

## Lexical structure

| Element | Rule | Status |
| --- | --- | --- |
| Source text | Strict UTF-8; identifiers are ASCII `[A-Za-z_][A-Za-z0-9_]*`; string and character contents may be Unicode ([bytes and text](first-release.md#bytes-and-text)) | P |
| Comments | `//` to end of line; consecutive `///` lines before a declaration are its [documentation](authoring-tools.md#documentation-comments) | P |
| Keywords | Reserved by the [lexer](../../../tools/vela/parser/lexer.mll); extension keywords are reserved even where no consumer accepts them | S |
| Naming | Types, constructors, members and type parameters use PascalCase; locals and parameters use camelCase ([common style](authoring-tools.md#common-style)) | M |
| Integer literals | Decimal, `0x` hexadecimal and `0b` binary digits with `_` [separators](authoring-tools.md#numeric-separators); a representation suffix (`0usize`, `0byte`) or the expected type selects the type | P (decimal `Nat`), M |
| Other literals | `true`, `false`, `()`, characters `'a'` with escapes, strings `"..."`, raw strings `"""..."""` and format templates `$"...{hole}..."` | P (`true`, `false`), M |

Token shape alone decides the syntax tree: there is no symbol table, type or
import-order input to parsing, and Menhir generation is strict and
conflict-free ([no ambiguous syntax](verification-strategy.md#permanent-language-exclusions)).
In patterns, an identifier beginning with an uppercase letter is a constructor
and a lowercase identifier binds.

## Declarations

| Construct | Syntax | Status |
| --- | --- | --- |
| Module | `module Name.Path;` opens every file | P |
| Import | `import Vela.Numerics;`, with qualified names resolved independently of import order | M |
| Visibility | `public` or `private` on each declaration | M |
| Constant | `const T Name = expression;` at module or local scope, evaluated during compilation ([required-static constants](surface-grammar.md#required-static-constants)) | P |
| Function | Type-first `T Name(T1 a, T2 b) { ... }` or `=> expression;` | P |
| Constant-compatible function and static parameter | `const T Name(...)`; `T Name(const U config, V value)` | P |
| Mathematical definition | `definition T Name(...) => expression;`, with no runtime representation implied | M |
| Theorem and lemma | `theorem Name(...) ensures P proof { ... }`; `lemma` likewise | M |
| Record | `record Name(T1 Field1, ...)` with optional `invariant` clauses and a member body | M |
| Struct | `struct Name<...> { private fields; view ...; members }` | S |
| Union | `union Name { Case1(T x); Case2(); }`; nullary cases are declared with `()` and written bare in patterns and expressions | M |
| Property | `public T Name => expression;`: total, effect-free and allocation-free | M |
| Interface and implementation | `interface Name<T> { ... }`, `impl<...> Name<...> { ... }`, used through `where Name(type T)` | M |
| Inductive and coinductive types | `inductive Name { Ctor(...); }`, `coinductive Name<T> { ... }` | S |

**Parsed example** (module, constant, functions and a static parameter):

```text
module Reference.Basics;

public const Nat Limit = 16;
public const Nat Twice(Nat x) => x + x;
public Nat Scale(const Nat factor, Nat value)
{
    const Nat multiplier = Twice(factor);
    return multiplier * value;
}
```

**Parsed example** (record with a named invariant, a property and a union):

```text
module Reference.Data;

public record Window(Nat Start, Nat Count)
    invariant Bounded: Start + Count <= 4096
{
    public Nat End => this.Start + this.Count;
}

public union Shape
{
    Point();
    Segment(Nat length);
}
```

**Parsed example** (interface, implementation and constrained use):

```text
module Reference.Interfaces;

public interface Sized<T>
{
    Nat Size(T value);
}

public impl Sized<Nat>
{
    Nat Size(Nat value) => value;
}

public Nat Total<T>(T first, T second) where Sized(type T)
    => Sized.Size(first) + Sized.Size(second);
```

## Types

| Type | Meaning | Status |
| --- | --- | --- |
| `bool`, `Unit` | Exactly `false`/`true`, and the single value `()`; no integer truthiness | P (`bool`), M |
| `Nat` | Mathematical natural; runtime use needs a selected representation and range relation | P |
| `u8`…`u64`, `i8`…`i64`, `byte`, `usize` | Fixed-width target integers; `usize` has the target's XLEN width ([primitive semantics](first-release.md#primitive-semantics)) | M (closed values) |
| `int`, `uint`, `long`, `ulong` | Exact aliases exported by `Vela.Numerics`, requiring import or qualification | M |
| `char` | One Unicode scalar value | M |
| Tuples `(A, B)` | Products, eliminated by tuple patterns | M |
| `Option<T>`, `Result<T, E>` | Library unions with `Some(v)`/`None` and `Ok(v)`/`Err(e)`; absence and failure are explicit cases | M |
| `Seq<T>`, `Vec<T, n>` | Specification sequence, and a mathematical vector of length `n` | M |
| `Span<byte>` | Concrete capability-and-memory carrier of the first slice | M |
| `Span<T, count>` | View of `count` initialized elements with runtime `Length` and erased `Model : Seq<T>` | D ([ownership libraries](first-release.md#ownership-libraries)) |
| `Slots<T, capacity>` | Vacant-slot storage with live-prefix and vacant-suffix ranges | M |
| `TextBuilder<capacity>` | Bounded text buffer for allocation-free formatting | M |
| Generics `<T>`, `<ghost Nat n>` | Type parameters and erased value indices; declaration generics are rigid | M |
| `Type`, `Type<n>`, `Prop`, `Fn(A a) -> B` | Universes, propositions and dependent function types | M |
| `ghost T` | Erased, duplicable specification data with no computation use | M |
| `tracked T` | Erased resource evidence that cannot be copied | S |
| `Fn`, `FnMut`, `FnOnce` with `captures C` | Shared-call, exclusive-call and consuming-call function types with their capture sets | S |

There are no implicit conversions: use `T.From(x)` for infallible widening and
`T.TryFrom(x)` for a range-checked `Result`. There is no `null`, `T?` or
automatic `T`/`Option<T>` conversion
([exclusions](verification-strategy.md#permanent-language-exclusions)).

**Parsed example** (generic and dependent signatures):

```text
module Reference.Types;

public definition T Identity<T>(T value) => value;
public definition Nat Length<T, ghost Nat n>(Vec<T, n> items) => n;
```

## Bindings

| Construct | Syntax | Status |
| --- | --- | --- |
| Immutable local | `let name = e;` or `let T name = e;` | P |
| Mutable local | `var name = e;` or `var T name = e;` | M |
| Local constant | `const T name = e;`, required-static | P |
| Pattern binding | `let (owner, receipt) = pair;`, `let Ready(buffer) = outcome;` | M |
| Early-exit guard | `let Some(v) = e else { return ...; }`, whose `else` block must leave the scope | M |
| Expression-local binding | `let name = e in body` | M |

Every local starts with `let`, `var` or `const`; a bare `T name = e;` is not a
local declaration. `let` makes the binding immutable but does not forbid writing
through an exclusive loan it holds. Type annotation and mutability are
independent choices ([binding table](verification-strategy.md#surface-conventions)).

**Parsed example** (settled local spellings):

```text
module Reference.Bindings;

public Nat Sum(Option<Nat> maybe, Nat base)
{
    let Some(extra) = maybe else { return base; }
    var Nat total = base;
    total += extra;
    return total;
}
```

## Expressions and operators

Operators from weakest to strongest binding, as fixed by the
[parser](../../../tools/vela/parser/parser.mly):

| Level | Operators and forms | Associativity | Status |
| --- | --- | --- | --- |
| 1 | Lambdas `x => e`, quantifiers `forall (T x) => P`, `let ... in`, `if (c) a else b` | Extend right | M |
| 2 | Implication `==>`, equivalence `<==>` | Right | S |
| 3 | `\|\|` | Left | P |
| 4 | `&&` | Left | P |
| 5 | `==`, `!=`, `<`, `<=`, `>`, `>=`, `e is Pattern` | None | P (`is`: M) |
| 6 | Range `a..b` | None | M |
| 7 | Bitwise `\|` | Left | S |
| 8 | Bitwise `^` | Left | S |
| 9 | Bitwise `&` | Left | M |
| 10 | `+`, `-` | Left | P |
| 11 | `*`, `/`, `%` | Left | P |
| 12 | Record update `e with { Field = v, ... }` | Left | M |
| 13 | Prefix `!`, `-`, `~`, `*p`, `&place`, `move`, `in`, `ref`, `out` | Right | P (`!`), M (`-`, `in`, `ref`, `out`), S (rest) |
| 14 | Postfix call `f(...)`, member `.Name`, index `e[i]`, generic `F<T>(...)`, `F::<T>`, propagation `e?` | Left | P (calls), M |
| 15 | Literals, names, `(e)`, tuples, `match`, holes `?name`, operator values `(+)` | n/a | P (literals, names, grouping), M |

Comparisons do not chain; parenthesize them. Short-circuit `&&` and `||`
evaluate the right operand only when needed. A `<` begins a generic call only
when a complete argument list closes and is followed by `(`
([token-only rule](surface-grammar.md#familiar-authoring-migration)).

Ordinary `+`, `-` and `*` compute the exact result and owe a proof that it is
representable in the result type; `/` and `%` additionally require a nonzero
divisor. Named `Checked*`, `Wrapping*` and `Saturating*` operations give other
behavior explicitly ([primitive semantics](first-release.md#primitive-semantics)).
The pure prototype's demonstration `Nat` arithmetic is total instead, with
saturating subtraction and `n / 0 == 0`
([natural division](vela-prototype.md#natural-division-and-remainder)); it
discharges no release obligation.

| Form | Meaning | Status |
| --- | --- | --- |
| Labeled call `Copy(in source, target: ref dst)` | A positional prefix, then labels naming the next declared parameters in order; no reordering or defaults | P |
| Member call `x.Method(a)` | Supplies the declaration's receiver loan; other arguments repeat their modes | M |
| Conditional `if (c) a else b` | Mandatory `else`; the same join as a two-arm match | M |
| Match expression | `match (e) { Pattern => value, ... }`, exhaustive, optional final comma | M |
| Pattern test `e is P` | Boolean test; `if (e is P)` binds `P`'s variables in the `then` branch | M |
| Record update `move base with { F = v }` | Declaration-order update; linear or affine records require `move` | M |
| Formatting `Format.Write(ref builder, $"n={n}")` | Writes into a bounded buffer, returning `Result<usize, CapacityError>`; no heap string | M |

**Parsed example** (operators, a conditional expression and a match):

```text
module Reference.Expressions;

public Nat Clamp(Nat value, Nat limit)
    => if (value <= limit) value else limit;
public bool InRange(Nat value, Nat low, Nat high)
    => low <= value && value < high;
public Nat Headroom(Option<Nat> used, Nat capacity)
    => match (used) { Some(count) => capacity - count, None => capacity, };
```

## Statements and control flow

| Construct | Syntax | Status |
| --- | --- | --- |
| Block and return | `{ ...; return e; }`; an expression body checks as one return | P |
| Conditional statement | `if (c) { ... } else { ... }` | P |
| Match statement | `match (e) { Pattern => { ... }, ... }`, exhaustive | M |
| Range loop | `foreach (let i in low..high) invariant P { ... }` | M |
| Collection loop | `foreach (let x in xs)`, `foreach (in x in xs)`, `foreach (ref x in xs)`: value, shared-read and exclusive element iteration | M (located modes); D (represented iteration) |
| While loop | `while (c) invariant P decreases m { ... }` | M |
| `break`, `continue` | Leave or restart the innermost loop, closing local loans | M |
| Assignment | `x = e;`, `x += e;` and the other compound forms, on `var` locals, fields and indexed elements | M |
| Propagation | `e?` returns `Err(e)` or `None` from the enclosing function; it is not C#'s `?.` | M |

A range loop supplies its bound, a representable increment and its decreasing
measure; only the functional invariant is authored. Every loop exit closes the
loans opened in the iteration ([loans and control flow](core-design.md#loans-and-control-flow)).

**Parsed example** (statement match with settled arms and bare `None`):

```text
module Reference.Control;

public Nat CountSome(Option<Nat> first, Option<Nat> second)
{
    var Nat count = 0;
    match (first)
    {
        Some(value) => { count += 1; },
        None => { },
    }
    if (second is Some(other)) { count += 1; }
    return count;
}
```

**Parsed example** (a bounded loop with its invariant):

```text
module Reference.Loops;

public Nat CountTo(Nat limit)
{
    var Nat count = 0;
    foreach (let index in 0..limit)
        invariant count == index
    {
        count += 1;
    }
    return count;
}
```

## Loans and parameter modes

| Construct | Meaning | Status |
| --- | --- | --- |
| Value parameter `T x` | Passes a value; copying only where the value's resource rules permit | P |
| `owned T x` / `move x` | Consuming transfer; the moved-from binding is unusable | S |
| `in T x` / `in place` | Shared-read loan | M (`Span<byte>`), D (general) |
| `ref T x` / `ref place` | Initialized exclusive loan | M (`Span<byte>`), D (general) |
| `out T x` / `out place` | Initialization loan: no read before initialization, initialized on every normal return | M |
| Receiver `this`, `ref this.Tail` | The receiver and a receiver loan limited to a named view | M (`this`), S (views) |
| Named view `view Tail = slots[length], length grows;` | A part of a struct a signature can lend separately | S |
| Place-named loan `'input`, `'this.text`; `region 'r` | A loan tied to one parameter or field; a region parameter only where no place can be named | S |
| Returned loan `Result<ref<'table> V, E>` | A loan leaving with a result, with a `restores` contract for its end | S |
| `*p`, `&place`, `p + n`, `p[i]` | Typed pointer and place operations under access contracts | S |

Each ordinary loan argument repeats its mode at the call site; inference never
inserts `in`, `ref`, `out` or `move`. A loan ends at its last use, branch by
branch, and restoration is inferred rather than written. A receiver loan starts
before the explicit arguments are evaluated, and the first release has no
two-phase receiver borrows and no loans carried across loop iterations
([product costs](verification-strategy.md#language-product-contract)). The
[loan-analysis diagnostic](loan-analysis.md) experiments with inferred loan
ends over supplied flow facts; source loan checking is design work under the
[borrow-analysis promotion contract](core-design.md#borrow-analysis-promotion).

**Design example** (a place-named result view, after the
[primary design](verification-strategy.md#dependent-results-and-place-named-loans)):

```text
module Reference.Loans;

public record PacketView<region 'source>(
    usize Consumed,
    in<'source> Span<byte> Payload,
    ghost Header Header)
    invariant Encodes(Header, Payload.Model);

public Result<PacketView<'input>, ParseError> ParsePrefix(in Span<byte> input)
    effects reads(input)
    ensures result.Model == Format.ParsePrefix(input.Model);
```

## Contracts

| Clause | Meaning | Status |
| --- | --- | --- |
| `requires P` | Entry condition the caller proves | M |
| `ensures P` | Exit condition; `result` names the returned value and `old(e)` evaluates `e` at entry | M |
| `where Interface(type T)` | Interface constraint or precontract on generic parameters | M |
| `restores P` | Predicate over the lender that holds when a returned loan ends; `final(x)` is the value the loan leaves behind | D ([restoration contracts](verification-strategy.md#flow-sensitive-loans-and-restoration-contracts)) |
| `invariant Name: P` | Named record or struct invariant conjunct, or a loop invariant | M |
| `decreases m` | Termination measure of a recursive definition or loop | M |
| `effects reads(a), writes(b), calls(f)` | Closed upper bound on reads, writes and calls, including transitive callees and captures; no allocation | S |
| `open (ref this, ref d) lifts A, B { ... }` | Opens only the listed invariant conjuncts; unlifted conjuncts stay in force, and the block must re-establish the lifted ones before any exit | M |

A `ref` view parameter's descriptor metadata (base, length and permissions) is
preserved by the call as an implied property of the mode; contracts state
content facts only. Exported `requires` and `ensures` clauses are obligations
under every preset; an unproved exported promise blocks acceptance. Public
`effects` lists are closed and propagate to callers, with no effect
polymorphism in the first release
([refinement, effects and staging](core-design.md#refinement-effects-and-staging)).

**Design example** (a returned exclusive loan with `restores` and `final`):

```text
module Reference.Contracts;

public Result<ref<'table> Value, TableFull> FindOrInsert<ghost Nat capacity>(
    ref Table<Key, Value, capacity> table, Key key)
    effects writes(table)
    ensures result is Ok(slot) ==> slot == old(table.Model).GetOr(key, Value.Default)
    restores result is Ok(slot) ==> table.Model == old(table.Model).Set(key, final(slot))
    ensures result is Err(_) ==> table.Model == old(table.Model);
```

**Parsed example** (selective invariant lifting):

```text
module Reference.Lifting;

public struct Buffer<ghost Nat capacity>
{
    private usize length;
    private Slots<byte, capacity> slots;
    invariant InitializedPrefix: LivePrefix(this.slots, this.length);
    invariant VacantSuffix: VacantRange(this.slots, this.length, capacity);

    public void Push(ref this, byte item)
        requires this.length < capacity
    {
        open (ref this) lifts InitializedPrefix, VacantSuffix
        {
            this.slots = Slots.Write(this.slots, this.length, item);
            this.length += 1;
        }
    }
}
```

## Proof mode

| Construct | Meaning | Status |
| --- | --- | --- |
| `proof { ... }` | Proof block whose steps elaborate to checked obligations and erase from runtime code | M |
| `assert P;`, `assert P by e;`, `assert P by { ... }` | Intermediate fact, optionally justified by a lemma call or a nested proof block | M |
| `calc { assert a == b; assert b == c; }` | Calculational chain of transitive equalities | M |
| `forall (T x) => P`, `exists (T x) => P` | Quantified propositions; a quantifier at the root of a clause is parenthesized | M |
| Named hole `?name` | A typed hole keeping its expected proposition, locals and loans; the build reports it and nothing containing it is accepted | S |

Checking tries conversion, resource rules, linear arithmetic, domain lemmas and
explicit proof in that order; a timeout or unsupported formula leaves the goal
unresolved and proof search never weakens a contract
([refinement order](core-design.md#refinement-effects-and-staging)). Linear
arithmetic over bounded scalars is automatic; nonlinear facts need an explicit
step. [Typed holes and invalidation](core-design.md#typed-holes-and-invalidation)
own hole identity.

**Parsed example** (a lemma with a calculational proof):

```text
module Reference.Proofs;

public lemma AddZero(Nat n)
    ensures n + 0 == n
    proof
    {
        calc
        {
            assert n + 0 == n;
        }
        assert n + 0 == n;
    }
```

## Errors and failure

Executable failure is an explicit `Result` or `union` case. Vela has no
exceptions, panics, stack unwinding or `longjmp`
([R-05-100](../../spec.md#r-05-100)); an operation owes the absence of
unexpected traps under its entry conditions, and environmental faults keep the
target contract's classification ([loans and control flow](core-design.md#loans-and-control-flow)).
Checked arithmetic and conversions return `Result<T, ArithmeticError>` or
`Result<T, ConversionError>`. `e?` propagates an `Err` or `None` and keeps the
function's `out` initialization and cleanup duties. An unexamined `Result` or a
discarded tracked resource is an error, including `Result<Unit, E>`.

**Parsed example** (propagation and a checked operation):

```text
module Reference.Errors;

public Result<u32, ArithmeticError> AddTwice(u32 a, u32 b)
{
    let sum = CheckedAdd(a, b)?;
    return CheckedAdd(sum, b);
}
```

## Extensions outside the first release

These constructs are parsed or designed for consumer-gated extensions. They
define nothing in the first release; the [extension index](extensions/README.md)
lists their owners.

| Construct | Extension | Status |
| --- | --- | --- |
| `x @ q`, `grade q : D`, `domain` declarations | [Graded foundation](extensions/graded-foundation.md) | S |
| `effect`, `handle`, `resume`, `dispose`, `rehandle`, `shallow` | [Handlers](extensions/handlers-async.md) | S |
| `async`, `scope`, `spawn`, `await`, `commit`, `on cancel` | [Structured tasks](extensions/handlers-async.md) | S |
| Cells, snapshots and local aliases | [Interior mutability](extensions/interior-mutability.md) | D |
| Descriptors, derivation and generated declarations | [Metaprogramming](extensions/metaprogramming.md) | D |
| `machine`, `hardware`, `state`, `register`, `transition`, `rule`, `schedule` | [Whole-system authorship](extensions/unified-source-contract.md) | S |

`scope` names only a structured task scope; invariant lifting uses `open`.
