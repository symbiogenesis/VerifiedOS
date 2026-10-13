# Offline typed graph composer

`python tools/run.py composer compose INPUT --output out/graph.json` executes the
descriptor-only filter in [HandlerGraph.v](../../proofs/HandlerGraph.v). It emits
the finite graph in declaration order and reports how many declared edges it
filtered. Filtering a malformed edge follows `spec_compose`; it does not admit a
generation. Package-supplied scripts are absent from the input and never execute.
An install or uninstall recomposes the entire successor roster.

Schema 1 takes exactly `schema_version: 1`, `descriptors`, `roster`, `type_count`,
`intent_count`, `world_count`, `inventory`, `verified_parsers`, and
`ring_depth_ceiling`. Each descriptor has `package_id`, `desc_manifest`, and
`desc_edges`. Every edge has the ten natural-number fields of `HandlerGraph.Edge`,
using their `edge_` names. `roster` is an ordered list of unique descriptor indices;
`inventory` and `verified_parsers` are sets encoded as unique natural-number arrays.
The parser refuses unknown fields, negative numbers, booleans where naturals are
required, duplicate keys and duplicate package names. The descriptor schema is the
projection read by `spec_compose`; node admission and media-template binding are
separate obligations.

The graph contains `schema_version`, `descriptors_sha256`, `package_ids`, and
`graph`, whose fields are `graph_nodes` and `graph_edges`. Canonical bytes are UTF-8
JSON with sorted object keys, compact separators, literal Unicode and one final
LF. The descriptor digest uses the same encoding over the parsed document, with
the two finite sets sorted. The graph digest is SHA-256 over its exact bytes.
`validate_graph` regenerates and compares the graph and can require an exact,
ordered package-ID roster. Boot binding must also retain the descriptor source
identity and producer identity. A caller-supplied digest alone is insufficient.

`composer fixture --output out/composer-input.json` generates the reference's
synthetic descriptor projection. `composer compare` compares Python predicates
with a limited, fail-closed reader of the source's predicates and witness values.
`composer prove` compiles generated equalities between the executable results and
the actual Gallina reference, covering accepted output, every spoiled-edge and
dropped-conjunct case, and successor roster prefixes. It uses the locked Rocq
switch in the checkout's native guest lane, then kernel-checks the comparison;
logs remain under that lane's log directory. This finite comparison is not a
universal implementation proof. `test --only test_composer --slow` includes it in
a provisioned guest; ordinary host tests exercise the source comparison.

Real package descriptors, authenticated parser evidence, the real image roster,
generation admission and signatures remain joins. Input parser flags declare the
reference's predicates; they establish no parser proof. This tool does not choose
an intent vocabulary or ambiguity policy, implement the object router, or claim
the reference's media-template and runtime binding obligations.

## Production composition checkpoint

The [production input schema](composition.schema.json) and
[M8a input](m8a-composition.json) implement the first checkpoint of
[M7.1d's production composition contract](../../docs/implementation/contracts/boot-roster.md#production-composition-input-and-projections).
The real roster table owns membership, ranks and executable status. The input
maps each roster member to its package identity, existing source references and
producer manifest, and declares separate startup dependencies, supervisor
authority edges, typed handler descriptors and image imports. Sources and
producer manifests bind exact checkout-relative paths and SHA-256 digests.
The checked schema rejects additional fields, repeated JSON keys and floating
substitutes for the schema version or integer fields, including nested arrays.
Unresolved target slots remain null. The production graph boundary refuses a
malformed declared edge instead of silently dropping it through the fixture filter.

`python tools/run.py composer project tools/composer/m8a-composition.json --output tools/composer/generated`
generates the immutable typed C supervisor manifest and four JSON projections:
the manifest, typed graph input, recipe members and admission request skeleton.
Each projection binds the same input bytes, roster, configuration and projection
producer sources. The C manifest binds that identity in its generated comment;
the JSON manifest carries its full source bindings. Numeric policy fields have
the existing C manifest's meanings and capacity bounds. The bounded supervisor
host implementation revalidates and compiles this generated manifest. Its scalar
target retains the handwritten comparison manifest; generated-manifest target
integration remains open.

`composer project` preflights every projection destination before creating or
writing outputs. Resolved leaves must remain inside the selected output directory,
and no output may alias another output or a consumed composition input, roster,
configuration, projection producer, or declared member, producer, descriptor or
derivation source. The checks include hardlinked files. A forbidden later output
preserves the earlier projection files and all consumed bytes; this host preflight
does not establish an atomic filesystem snapshot. Normal regeneration remains
supported under `out/` and the documented checked-in projection directory.
The focused `test --only test_composition_publication` covers permitted regeneration,
input and transitive source collisions, file aliases and named CLI refusals;
the Linux lane also exercises real escaped leaf symlinks.

The input digest names the exact byte snapshot parsed and validated for those
projections, including its JSON formatting. A valid substitution between parsing
and binding receives a `stale source binding` refusal, rather than binding one
composition's manifest or relations to another composition's bytes. Build-record
generation and validation use the same checked snapshot for their projections
and final input binding, and refuse subsequent drift. Declared member, producer,
descriptor and derivation sources are also rechecked before projection or build
bindings publish. Projection binding follows descriptor expansion, so a source
substitution during that work cannot retain an earlier source identity.

Roster membership, ranks and executable status use one exact contract-byte
snapshot throughout validation, projections and build records. Publication
rechecks that snapshot's digest rather than hashing a new roster read. A rank or
status substitution after validation receives a `stale source binding` refusal;
unchanged roster semantics with different formatting remain accepted and bind
their own exact bytes.

`python tools/run.py composer check-project` regenerates and compares every
checked-in projection byte. A changed member, source, producer, relation,
placement or derivation reference invalidates the projections. The focused
`test --only test_composition` independently expects the six main-die members,
the `crypto-core`, `storage`, `copy-service` startup order and storage's
crypto-core dependency. It also exercises missing and duplicate members,
swapped package identities, conflicting order, invalid extents, stale bindings
and substituted derivation references. Fixture descriptor and recipe schemas
remain unchanged.

The M8a input explicitly leaves descriptors, target producers, placements,
entry products, admission tiers and derivation sources unresolved where the
products are absent. Its source list identifies existing statements and the
supervisor's comparison manifest; it does not make them target products. The
two existing offline reference tools have source-bound producer identities and
are excluded from admission certificates. Missing descriptors yield a null
graph document, rather than a fabricated graph. Present descriptors are checked
even if another member is unresolved. Each descriptor is parsed from the exact
byte snapshot checked against its source digest; a substitution after an earlier
binding read receives a `stale source binding` refusal. A declared graph context
checks every present edge against its owner's manifest, the full roster indices and the
declared type, intent, world, format, parser and ring limits before withholding
an incomplete graph. Absent graph choices remain unresolved. Once complete,
their document uses the existing composer schema; every descriptor source must
name its own package.
Image entries may be unresolved; a declared entry follows the boot contract's
`_start` rule. Planned text/data extents must fit executable/writable MainMemory,
with no overlap with each other, the graph reservation or aligned HTIF word.
Placement checks parse the exact configuration byte snapshot whose digest matches
the declared source binding. A valid memory-map substitution after an earlier
digest read receives a `stale source binding` refusal; configuration drift is also
rechecked before projections and build records publish their bindings. Unchanged
and differently formatted bound JSONC configurations remain accepted.
They reserve space rather than proving the size or identity of a built image.

`vos.composition.build_record` resolves runtime artifact slots to actual file
paths and digests after producing member bytes. It binds the input and all
projection digests, regenerates the graph and binds the final image bytes.
`validate_build_record` first refuses malformed root containers and missing or
extra root fields, then rechecks those inputs and bytes; it trusts no reported
admission boolean. It compares canonical JSON bytes with the regenerated record,
refusing boolean/integer/float type substitutions and malformed JSON content.
Artifact maps and runtime/image references also receive closed-shape and string-field
validation before their filesystem binding. Malformed containers, missing or extra
reference fields and non-string paths or digests return named composition refusals.
Runtime slots must name distinct resolved artifact paths;
relative path aliases cannot substitute one member's file for another. Distinct
files may carry identical bytes. The skeleton contains no final image digest or certificate,
and generated derivation references supply no proof evidence. Neither the byte
binding API nor the generated files perform the M7.1c derivation checks.

`composer build-record INPUT --projections PROJECTION_DIRECTORY --artifacts ARTIFACT_PATHS --graph GRAPH --image IMAGE --output out/build-record.json`
publishes the build binding as canonical JSON after consuming the actual projection
files and produced bytes. `ARTIFACT_PATHS` is a JSON object mapping every runtime
artifact slot to its checkout-relative file path, for example
`"storage-artifact": "out/products/storage.elf"`. The command computes each file's
digest; the path map does not supply digests or admission claims. All input paths
stay inside the checkout. Output belongs under `out/` and cannot replace a consumed
input, product or transitively bound source. The checked-in projection directory
is the default when `--projections` is omitted.

`composer check-build-record INPUT --projections PROJECTION_DIRECTORY --record RECORD --graph GRAPH --image IMAGE`
revalidates a saved record against those published projections, the current runtime
artifacts, graph and final image. It writes no files. Changed projections, produced
bytes or source bindings refuse; an unresolved graph also prevents record generation.
Both operations retain `production_admission: false`. The focused
`test --only test_composition_build_cli` covers the canonical round trip, publication
and byte substitutions, malformed path maps, output aliases and unresolved inputs.

`composer promote INPUT` refuses the roster's incomplete members and the absent
production admission implementation. M7.1a placement/image construction, M7.1b
manifest admission and target execution, real producer/descriptor adapters,
full-roster boot and fault/restart observations remain joins.
