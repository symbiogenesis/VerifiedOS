# Vela formatting, documentation and lints

This contract owns [Q25r, Q25s and Q25t](../../../PLAN.md#q-assessment-actions).
The [surface grammar](surface-grammar.md) owns syntax and the
[pure prototype](vela-prototype.md) owns its executable semantic boundary.
The compiler includes a formatter and lint pass, enabled by default. The initial
executable formatter and lints cover that pure subset; wider formatting and
semantic lints consume their qualified parser/frontend producers through
[compiler services](tooling-protocols.md#compiler-inspection-api).

## Common style

Style version 1 takes its C# layout and naming conventions from
[StyleCop](https://dotnetanalyzers.github.io/StyleCopAnalyzers/), including
[Allman braces](https://github.com/DotNetAnalyzers/StyleCopAnalyzers/blob/master/documentation/SA1500.md),
[upper-case member initials](https://github.com/DotNetAnalyzers/StyleCopAnalyzers/blob/master/documentation/SA1300.md)
and [lower-case parameter initials](https://github.com/DotNetAnalyzers/StyleCopAnalyzers/blob/master/documentation/SA1313.md).
[Clippy's lint levels](https://doc.rust-lang.org/clippy/usage.html) inform the
toolchain integration. This is a Vela style, not a claim to implement every
StyleCop or Clippy rule; neither upstream implementation is incorporated.

- Use four spaces per indentation level, LF newlines and one terminal newline.
  Opening and closing block braces occupy their own lines; `else` starts a new
  line. Separate top-level declarations with one blank line and keep attached
  documentation directly above its declaration.
- Use one statement per line, one space around binary operators and after commas,
  no space before a call's opening parenthesis, and a space after control keywords.
  Grouping parentheses have no internal padding. Preserve the authored choice
  between a return block and an expression body.
- Public functions, constants and user-defined types use PascalCase; parameters
  and local bindings use camelCase. The formatter never renames symbols.
  Primitive spellings, lifetime identities, grade names and foreign names retain
  their defining contracts; naming is a suppressible lint, not parsing authority.
- Declaration contracts occupy separate indented lines before the body. Long
  signatures and calls may wrap at argument boundaries with one extra indentation
  level; width is guidance, not a source acceptance limit. Keep ownership, loan,
  effect and proof annotations visible and in their authored order.
- Preserve token spellings, literal representations, comments and documentation
  contents. Do not sort imports, declarations or arguments, insert conversions,
  change parentheses or synthesize proof, resource or disposal operations.

```text
module Example;

/// Computes the configured capacity.
public const Nat Capacity = 1_024;

/// Scales a count by the configured capacity.
public Nat Scale(Nat count)
{
    return count * Capacity;
}
```

## Numeric separators

An underscore separates two digits of the same numeric base. Decimal literals
work in the pure and surface entries; hexadecimal and binary remain surface
features. Examples are `1_024`, `1_024usize`, `0xFF_FFu64` and `0b1010_0011byte`.
Leading, trailing and repeated separators are refused, including adjacency to a
base prefix or representation suffix. Suffix interpretation stays separate from
the digit run. Preserve raw source spelling and original byte spans in located
syntax; evaluation removes separators. Count actual digits, not underscores,
against the existing literal bound. Keep existing leading-zero and representation
rules. The mathematical consumer and pure translation agree with the corresponding
unseparated values; a representation suffix grants no new pure-subset type.

## Documentation comments

Consecutive `///` lines directly preceding a declaration form its documentation.
Strip the three slashes and at most one following space for presentation; retain
original UTF-8 text and source positions. A blank line, ordinary comment or
intervening source token breaks attachment. Orphan documentation remains a
comment. Formatting must preserve attachment and every comment's content.

Plain text is supported. C#-style XML documentation may be preserved as authored
text; accepting comment text does not promise XML validation, entity expansion,
external reference fetching or inherited documentation. Documentation is distinct
from executable contracts, checked propositions and evidence status.

The compiler attaches documentation to its resolved declaration facts. Existing
hover presents it as bounded plain text; references show the declaration's
documentation, not nearby comments at a use site. Protocol projection validates
source binding and limits, and never reparses or resolves declarations itself.
The existing parser schemas need no invented documentation fields. Unsupported
surface declarations retain their comments without acquiring semantic facts.

## Compiler commands and publication

`vela fmt SOURCE` writes canonical formatting; `--check` reports differences
without writing. `vela lint SOURCE` reports the supported lint set without
rewriting. Ordinary `vela check SOURCE` and `vela emit SOURCE` run formatting and
linting automatically. `--format check` makes formatting differences a failing
read-only check; `--format off` leaves source bytes intact. `--no-lint` disables
optional lints, never parser, type, constant-evaluation or proof obligations.

Validate the complete source before default rewriting. Reparse and recheck the
formatted candidate, establish token/comment preservation and idempotence, and
publish changes atomically only to the same unchanged regular source file.
Refuse symbolic links and changed inputs rather than overwriting another file or
another editor's work. Failed syntax/type checks, denied lints or invalid output
destinations leave source and generated output intact. Diagnostics and emitted
source hashes bind the exact snapshot used for compilation; after formatting,
recompute semantic facts and emission from the new bytes. An I/O failure after
source publication may leave a formatted source but must not claim successful
output publication. The library checker and language server never rewrite files.

## Lint policy

Lints have stable Vela IDs, locations and explicit messages. Default advisory
warnings cover member/binding naming, missing public documentation and redundant
Boolean-literal comparisons. Only compiler-supported syntax or resolved facts
justify a finding; no heuristic borrow, effect, termination or proof verdict is
invented. Emit no semantic/style finding for a source that failed complete checking.
Lints never rewrite code automatically.

Repeatable `--allow ID` suppresses optional findings; `--deny ID` makes them
errors. The same ID cannot be both allowed and denied. Unknown IDs are command
errors. Defaults and rule identities are compiler-versioned; disabling an optional
lint cannot waive a language error. Findings go to stderr, keeping emitted Gallina
on stdout usable. A denied finding prevents default formatting and output writes.

## Qualification

Q25r requires independently expected separator values/spans in both parser
entries, pure-route and mathematical agreement, constants, literal patterns and
generic arguments, all bases/suffix boundaries, malformed neighbors and actual
digit limits. Retain strict conflict-free native generation and byte-identical
regeneration. Native generation and replay acceptance run on hosted Guest CI.

Q25s requires direct-declaration attachment and orphan/break cases, Unicode and
mixed newlines, declaration/use hover agreement, versioned edit invalidation,
bounded text, forged/stale documentation refusal and a real stdio session. Existing
two-editor interoperability qualification remains with Q25n/Q25o.

Q25t requires independently expected formatting and lint findings, idempotence,
unchanged ordered tokens/comments and equivalent reparsed syntax apart from
locations. Compose named arguments, constants, expression bodies, nesting,
comments and numeric separators. Verify default rewriting, check/off modes,
allow/deny and invalid-ID behavior, stdout/stderr separation, exact post-format
provenance and refusal without writes for invalid, unsupported, oversized, aliased,
changed or nonregular input/output. Run focused host tests and Python checks;
require both Host CI aggregates and dispatch every Guest CI lane for the settled
revision. Wider-language qualification remains with its frontend owners.
