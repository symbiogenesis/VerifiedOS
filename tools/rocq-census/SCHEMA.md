# Native census provenance wire contract

[census-schema.json](census-schema.json) describes `verifiedos-sail-support-census/1`
using JSON Schema Draft 2020-12. This is a new, unqualified native provenance format;
it neither changes `verifiedos-rocq-native-metadata/1` nor supplies an acceptance
verdict. The [owner contract](../../docs/implementation/contracts/sail-support-census.md)
owns qualification. Unsupported, ambiguous or incomplete native shapes refuse the
producer process explicitly; they never yield a successful truncated census.

## Invocation and ownership

The runner performs each exact requested root's original Search query first. It
supplies `VOS_CENSUS_TARGETS` as the existing comma-separated exact requested root
names. Resolution requests use exactly one of `VOS_CENSUS_RESOLVE`, carrying an
ordered JSON array, or `VOS_CENSUS_RESOLVE_FILE`, naming an absolute regular JSON
input file. Supplying both refuses. The file form avoids native environment-string
size limits for the complete population; it is bounded at 64 MiB, copied into the
private lane, and its exact bytes and path are hash-bound before launch and checked
after execution. It contains request data only. Both forms have the same wire shape:

```json
[{"id":"SailStdpp.TypeCasts:0","requested_root":"SailStdpp.TypeCasts","row_index":0,"spelling":"TypeCasts.Z_eq_dec.U"}]
```

Retain the file-form bytes with the raw Search evidence. Replay checks them against
the exact ordered requests derived from those rows and the producer's echoed
`resolution_requests`. A missing, changed, oversized or unreadable file refuses;
the runner clears the unused request variable explicitly between invocations.

`row_index` is zero-based in that root's parsed Search declarations. The request ID
is the exact requested root, a colon and the decimal row index. Repeated spellings
remain separate requests. Duplicate request IDs or duplicate native Search rows
refuse; they must not be normalized away. The runner does not infer a native root ID.
The producer emits the exact `resolution_requests` in input order, an exact ordered
`resolutions` answer for each request, and `roots` in `requested_roots` order. Each
answer binds the request to the native root's `module_id`. Its single candidate
identifies exactly one enumerated declaration or abbreviation, never both.
`mode: global` requires an actual native global lookup and the declaration's
`field_id`; `mode: interface-field` requires native structural field resolution
and that abstract declaration's `field_id`, without a global-lookup claim.
An interface candidate's reference identifies its native field, while the
declaration's `native_reference` stays null and it receives no assumption query.
`mode: abbreviation` has null `field_id` and names the independently enumerated
abbreviation. Consumers enforce these alternatives against the enclosing context;
the presence of a reference alone never establishes a global declaration.

The runner binds complete raw Search, Print Module and Print Module Type readings
and input identities separately. Every module's `query` names an actually queryable
module or module type and its `target_module_id`; `coverage_path` structurally reaches
the represented module from that reading. A non-queryable functor parameter/result
uses the enclosing reading and an explicit parameter/result path. It does not
invent a queryable name for an abstract field. `owner_root_id` retains the requested
root whose query population owns that reading. Repeated query targets need one
complete retained reading, with every consuming structural link preserved.

## Structural population and contexts

IDs are stable strings derived deterministically from the native path, context,
namespace and indices they identify. Consumers treat them as keys and verify every
join; an ID string alone is no ownership evidence. Every table has unique IDs.
`field.namespace` is `module` for modules/module types and `object` for constants and
mutual inductives. A structure may legally contain the same label once in each
namespace. Duplicate `(parent_module_id, namespace, label)` tuples refuse.

For each module, `signature.field_count` equals the exact native NoFunctor body's
length and `field_ids` preserves its field order. These IDs biject precisely the
fields with that `parent_module_id`. Every module/module-type field has exactly one
`child_module_id`; child records point back through `parent_field_id`. Root and
functor-parameter-signature modules have no parent field. Each ordered functor
parameter identifies its native bound module, signature module and context; the
result context retains its enclosing chain. Every field/declaration context must
agree with that chain. Context kinds, rather than a supplied classification string,
determine whether a declaration is abstract. Module-type fields and unapplied
functor parameter/result fields remain `interface`, including definitions and
inductives within them. They receive no global assumption query.

A constant field has one constant declaration. A mutual-inductive field has one
inductive declaration per packet and one constructor declaration per constructor,
in native packet/constructor order. `packet_count`, `constructor_count`, declaration
indices and every declaration's `type` must agree with the field metadata. Packet
indices are zero-based; constructor indices are one-based. Module fields have null
metadata and no declaration IDs. Object fields have non-null corresponding metadata
and null child modules. Declarations repeat the field's context and classification.
All references and metadata preserve native order. Set-like native tables are
emitted deterministically by their native key order.

`native_reference` is null for an uninstantiated interface declaration. Concrete
references contain actual native user/canonical kernel names, native printable
`exported_name`/`canonical_name`, kind and applicable indices; absent indices are
null. Consumers never repair a prefix or derive a foreign owner from a short name.
The independently established canonical instantiated exported global is the owned
symbol passed to the unchanged common guard. External canonical targets require
explicit proven alias classification and stay outside that owned list.

Private implementation references are a separate `kernel_reference` shape:
`kind`, actual native `user` and `canonical` kernel names, and applicable packet
and constructor indices. It has no printable global names. Only connection
`source_reference`, `implementation_reference` and declaration-alias
`target_reference` use this shape. Generic functor fields and private originals
need not be registered globals; their structural identities and native before/after
metadata establish the substitution join. They receive no global lookup or
assumption-query claim. Exported concrete references, resolution candidates and
direct-reference abbreviations retain the full global-reference shape and their
independent native global resolution and audit requirements.

## Concrete implementation evidence

Every owned concrete declaration has a non-null `implementation_connection` and
null `alias`. Every alias declaration has complete `alias` provenance and a non-null
implementation connection. Every interface declaration has neither. A concrete
connection retains the exported global, the actual source and instantiated fields,
source and instantiated declaration metadata, actual native references, and a
nonempty ordered resolution trace with `lookup_succeeded: true`. A status label or
printed signature is insufficient.

A `direct-lookup` step requires an actual native declaration lookup. A sealed field
must additionally follow its module implementation: `FullStruct` selects the native
signature body; `Struct` retains the separate implementation structure; `Algebraic`
retains and follows its expression. Every alias/application/substitution step names
its native expression, bound identifier/argument or before/after field, and resolver.
Unapplied functors and `Abstract` supply no concrete implementation connection.
Source and instantiated metadata must be the actual native readings before and
after the recorded substitutions. Do not re-elaborate or typecheck private sealed
implementation terms in the ambient environment.

`module_descents` retains enclosing implementation provenance once per concrete
nested module. Its `owner_module_id` is the exported child, and its module-namespace
source/instantiated field locators select the same label with null packet and
constructor indices. Each native child module's path is its locator's parent path
plus that label; the instantiated path equals the flat exported child's native
path. The instantiated locator's parent is the flat native parent module.
`source_module` is the original implementation child before the parent's native
substitution; `instantiated_module` is the actual child after it. Preserve both
complete native module readings. A private instantiated signature need not equal
the public sealed signature.
`field_selection_succeeded: true` records the actual selections from both native
parent bodies. It claims no global lookup of an original uninstantiated child.

Every concrete nested module has exactly one descent, including an identity
descent through an ordinary structure. Requested roots have none. Modules whose
result context is an interface or unapplied functor have no concrete descent.
`parent_descent_id` identifies the direct parent's descent, or is null when that
parent is a requested root. The descent's steps evaluate the parent's own local
implementation, select exactly one actual module-namespace structure field, and
optionally finish with the aggregate native source-child to instantiated-child
substitution. No module is represented as a global constant lookup.
Parent evaluation is anchored to the parent's descent's instantiated private
implementation, or the requested root's implementation when the parent is a root.

Every object connection's `enclosing_descent_ids` is the exact outermost-to-owner
descent chain, empty for an object in a requested root. Its local `steps` evaluate
the child's implementation and select the actual object field, then apply any
aggregate native substitution and perform the exported global lookup. Dropping a
parent functor substitution or relabeling an already substituted child as its
original source refuses. Consumers verify descent population, parent links,
namespaces, paths, ordered traces and complete metadata, alongside the existing
object connection checks. The native producer retains and applies actual native
substitutions; the wire evidence never substitutes for them.
Local object evaluation is anchored to its owner's descent's instantiated private
implementation, or the root implementation for a root-owned object.

`audit_query_name` names the independently resolved instantiated exported global,
not an uninstantiated functor source or fabricated external alias. Locked native
Print Assumptions follows that exported name to its implementation; it remains the
assumption oracle. The producer emits no assumption verdict. The adapter and runner
must preserve the visible/exported identity separately from implementation aliases.
A source reference is provenance, not permission to assumption-query it.

## Required metadata and finite resolver domain

The schema fixes constructor-based terms, relevance/casts/cases, recursive binders,
projections, local contexts, abstract universes and constraints, typing flags and
conversion-oracle strategies, inductive template/variance/record metadata, and
module implementation/algebraic-type expressions. Every `transparent_body` is
null: the producer never exports executable library bodies. Exactly `Def` has a
non-null `transparent_body_identity`, using native OCaml `Digest.BLAKE256` over
the complete deterministic constructor JSON under
`verifiedos-rocq-native-term-json/1`. Its `digest` is exactly 64 lowercase hex
characters. The producer computes and discards this encoding in memory, with no
temporary body file. The identity retains the complete, deduplicated native
`module_paths` and `kernel_names` collected during that traversal, in native key
order. Source and instantiated identities can differ after substitution; neither
equality nor a digest alone proves the implementation connection. Native
substitution provenance and `Print Assumptions` retain their existing duties.
Every other body kind has null `transparent_body_identity`. Only `Undef` may have an
inline level; only `Primitive` has a non-null primitive identifier. Opaque proof
bodies remain under the native assumption oracle. This type/provenance format does
not serialize VM code, opaque proof storage, or derived recursion automata.

Global monomorphic universe constraints come from the complete native universe
graph, retaining every node/alias/edge and its unsafe-mode flag. The quality graph
retains its complete domain, complete constraints and ignore-constraints flag. It
is not a per-declaration constraint attribution. Native module bodies at this lock
have no independent module-constraints field. Polymorphic contexts remain attached
to their actual declarations and module-expression refinements.

A delta resolver is opaque in the public locked API. `resolvers` explicitly records
`finite-enumerated-domain`: its native root, effects on every enumerated module
path and every kernel name occurring in fields, references, expressions, types,
transparent-body reference domains, source/instantiated metadata and connection traces, plus every
native `inline_of_delta None` key/level. Each native resolver is separately named
by owner and role; unrelated domains or identity effects cannot be dropped.
Inline keys also receive kernel effects. Completeness is checked against that
finite union. These effects are not a serialization of the hidden resolver object.
The actual native resolver is used for substitutions; textual effects never replace
it. An unavailable effect or unaccounted reference refuses.

The producer enumerates the native abbreviation map independently of Search.
Every abbreviation whose absolute path is owned by an enumerated module appears
once and is linked through `abbreviation_ids`. Version 1 supports proven direct
reference abbreviations with no bound variables; any other owned abbreviation
shape explicitly refuses. `native-empty` requires a complete zero-field native
body and no abbreviations. `native-alias-only` requires a complete zero-field body
and nonempty, completely proven abbreviations. Nonempty bodies use `nonempty`.
An empty Search result never establishes either empty classification.

Schema validation checks shapes. Consumers must also enforce every population,
namespace, context, reference, trace, finite-domain and ordering invariant above,
account for every raw Search row, and refuse unsupported native forms (including
Meta/Evar, rewrite rules or symbols). Positive/refusal native controls and the real
hosted exact-assumption/recursive-kernel join remain separate acceptance evidence.
