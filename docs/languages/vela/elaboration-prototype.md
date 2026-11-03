# Vela mathematical elaboration prototype

## Commission and boundary

[Q25k](../../../PLAN.md#q-assessment-actions) commissions an opt-in, bounded
extension of the [pure prototype](vela-prototype.md). Its source means the emitted
CIC term. It introduces no independent source semantics, production frontend,
machine representation, resource interpretation or binary admission. The
[full-language hold](full-language-review.md#r-05-009-r-05-020-and-what-holds-the-frontend-rows)
and [unified-source acceptance](unified-source-contract.md) remain outstanding.
Land this contract and its checklist predicate before implementation.

The pure checker, schema-1 protocol and parser migration comparison retain
their contracts. Mathematical elaboration consumes the Menhir surface
entry point and schema 2, with no second surface parser. Generated Gallina is an
untrusted proposal until the pinned Rocq kernel checks it. A source digest binds
bytes; it supplies no source-correspondence theorem.

The [staged metaprogramming design](metaprogramming.md) extends the intended
language beyond this increment. Type-valued parameters, definitional reduction
and the compositional constant interface support the bounded mathematical fragment.
General descriptor reflection, generated declaration APIs and composition with
the refused resource/effect features remain outside it.

## Supported mathematical increment

The increment uses the [surface grammar](surface-grammar.md). Its current executable
examples retain `definition ... = expression;`, explicit `::<...>` application
and the current match-arm delimiters. The selected [familiar authoring migration](surface-grammar.md#familiar-authoring-migration)
belongs to Q25z and changes this consumer only after its parsing, interpretation,
source-binding and kernel-replay predicates qualify together.

The supported increment includes:

- Generic type and stable ghost-value telescopes, explicit `::<...>` application
  and fresh inferred instantiation at each use. Generic variables in a
  declaration are rigid; inference cannot specialize its promised signature.
- Numeric predicative universes `Type` and `Type<n>` for levels zero through
  eight, dependent `Fn` telescopes, type-valued parameters and
  computed types. Substitution preserves dependency and avoids capture. Reject
  self-typing universes and escaping inference variables. Symbolic universe
  declarations, implicit cumulativity and universe-level inference remain
  unsupported; universe levels match exactly. Use `<P : Prop>` for a
  proof-polymorphic routine.
- Bidirectional inference for applications, immutable locals, products and
  higher-order functions. Expected types constrain lambdas and omitted generic
  arguments. An annotation hole `_` requests inference, never an axiom. Ambiguous
  or unresolved variables are errors. No implicit numeric or option coercions.
- Calls use positional arguments or a positional prefix followed by a labeled
  suffix. Each label must match the next declared value parameter, including
  named `Fn` parameters; unnamed callable parameters accept no labels. No
  argument reordering, omission or defaults are inferred. Dependent later
  parameters are instantiated in declaration order before their arguments are
  checked, preserving complete telescope substitution.
- Mathematical `Nat`, `bool`, `Unit`, products, equality propositions and explicit
  proof constructors. Indexed vectors and finite indices provide a concrete
  dependent collection boundary, including length preservation and safe lookup.
- Typed `const` values of `Nat`, `bool` or `Unit`, at module or local scope,
  under the [required-static contract](surface-grammar.md#required-static-constants).
  Initializers use earlier constants and admitted total pure calls with static
  arguments and explicit static parameters; unmarked outer runtime parameters,
  ordinary locals and generic or ghost indices are refused before reduction,
  including dead or ignored dependencies.
  Internal locals of a pure call evaluated with static arguments remain part of
  that evaluation. Emit the bounded evaluated value, with no runtime fallback.
  A constant can index `Vec<Nat, Limit>` directly; it is a value, so `Limit()`
  is not a constant access. Represented machine types retain target prerequisites.
- Constant-compatible function modifiers and `const` value parameters use the
  same [compositional contract](surface-grammar.md#required-static-constants).
  The former preserves runtime calls; the latter requires static arguments and
  supports symbolic local constant computation. Static parameter requirements
  follow dependent function telescopes, partial applications and higher-order
  uses. A closed instantiation computes its demanded constants under the existing
  bounded reducer. Logical templates retain their interpretation in CIC; no
  production backend or runtime-storage guarantee is supplied by these terms.
- Aliases, definitions, returning pure functions, theorem/lemma bodies and
  immutable proof locals. Equality proofs are ordinary first-class values;
  theorem bodies must inhabit the declared proposition. Ordinary expression
  equality remains Boolean, while theorem equality denotes a proposition.

Source callable interfaces preserve explicit arity: `Fn() -> Unit` and
`Fn(Unit value) -> Unit` require different calls and lambda parameter lists even
though their CIC interpretations use unit. Neither named arguments nor unit
normalization supplies an omitted argument.

Inference uses bounded structural unification with occurs and scope checks and
bounded definitional conversion. It proves no arbitrary arithmetic equality and
uses no external solver. Reduction exhaustion is a limit diagnostic, never an
established equation. Every unsupported syntax role, effect, capture, resource
modifier, grade, contract or unfinished proof is refused explicitly. This
increment supplies theorem authorship and proof parameters; automatic discharge
of `requires`/`ensures` and the full proof language remain frontend work.

The implementation owns explicit finite source, syntax-depth, inference-work,
reduction and output limits. Diagnostics retain source positions and distinguish
unsupported syntax, names, typing, unresolved inference, protocol and limits.
The consumer validates schema, source digest, fields, spans and identifier
spellings before constructing terms. Hygienic generated names and a closed
builtin mapping prevent Gallina injection. No raw Gallina, axiom, admission,
unchecked hole or foreign proof escape is emitted.

## Commands and acceptance

`python tools/run.py vela-parser elaborate SOURCE` parses the complete surface,
elaborates this mathematical fragment and emits Gallina. `--output FILE` uses
atomic publication after complete validation and refuses input aliases. Missing
parents, malformed input and failed writes leave existing destinations intact.
The command runs through the existing guest dispatch because Menhir is native.
`vela-parser elaborate --help` documents development status and limits.

`python tools/run.py vela-parser elaborate-qualify` builds the pinned parser,
elaborates the authored example and independent positive/negative sources, then
kernel-checks emitted terms with the locked proof switch and recursively checks
the resulting library. Its receipt binds source, elaborator, parser and tool
identities. A rejected neighbor must reach its intended semantic diagnostic;
parse failure and unavailable tooling supply no semantic rejection evidence.
The model Guest CI lane runs this command. A kernel verdict covers generated
terms only, not checked parsing or source correspondence.

Independent focused host tests exercise fresh polymorphic instantiations,
explicit/inferred arguments, dependent substitution, vector lengths and finite
lookup, higher-order constraints, proof composition, definitional conversion,
determinism and name hygiene. Negative neighbors cover unequal indices, wrong
domains, false equality proofs, non-propositions, universe misuse, occurs/scope
failures, ambiguous holes, missing proof bodies, stale or malformed protocol,
unsupported contracts and resource syntax, and bounded failures. CLI controls
exercise atomic publication, input aliases and failure preservation. Native
qualification replays source through the actual parser and kernel rather than
only using hand-authored syntax fixtures.

Require focused tests, Python type/lint checks, the consistency checker, Host CI
on Windows and Ubuntu, and dispatch of every Guest CI lane at the settled
revision. Native acceptance remains pending until its exact-revision hosted
verdict exists. Finish without waiting for Guest CI. Keep Q25k open while that
predicate is outstanding, and report the supported fragment and remaining
production obligations in the command guide.

## Try the mathematical fragment

Run from the repository root on Windows, using `python3` on Linux:

```console
python tools/run.py vela-parser elaborate tools/vela/examples/dependent.vela
python tools/run.py vela-parser elaborate-qualify
```

The [example](../../../tools/vela/examples/dependent.vela) combines a generic
identity, higher-order application, inferred vector lengths, finite-index lookup,
a dependent callable and equality proofs. `elaborate` prints Gallina or writes
`--output FILE` in an existing directory. It requires the parser's locked native
toolchain; `elaborate-qualify` additionally requires the locked proof switch.
Only the latter command supplies a kernel verdict for its declared fixtures.

Generic parameters default to `Type`; `<T, ghost Nat n>` quantifies a type and
stable natural index. Each call infers new arguments, while `::<...>` supplies
them explicitly and `_` requests an inferred argument. A contextual lambda can
use `value => ...` or `(left, right) => ...`; omitted parameter annotations use
the same bounded expected-type inference as annotation holes. Missing type
information remains an error. Ordinary value-returning functions may use
`=> expression;` as the checked equivalent of a single return block.
Declare a dependent callable with
`Fn(Nat n, Vec<Nat, n> values) -> Vec<Nat, n>`.

`Fst` and `Snd` project ordinary products. `Vec<T,n>` is a mathematical indexed collection, with `VNil`, `VCons`, `Fin`,
`FZero`, `FSucc` and `At` for construction and safe lookup. This prototype gives
it no machine layout. Definitional equality is computational: use `Succ(n)` or
`1 + n` for a successor index; arbitrary rearrangement of natural arithmetic
needs an explicit theorem. `Refl`, `Symm`, `Trans` and `Congr` construct equality
evidence. Concrete product projections and finite lookup reduce during checking,
so the example proves its lookup result. `type[Eq::<T>(left, right)]` lets an
ordinary parameter carry that proof.
