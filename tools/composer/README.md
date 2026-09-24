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
