# Portable Sail assistance

## Delivery contract

This bounded tool-maintenance delivery makes the existing compiler-emitted Sail
documentation bundle available as context to any shell-capable agent. It uses the
locked Sail toolchain and the existing Python environment, with no new package,
service, model account, editor extension or agent-specific configuration.

Implementation begins after this contract is committed. Its acceptance predicate is:

- `python tools/run.py sail-context` provides ranked local example search, exact
  symbol lookup across declaration kinds and scattered clauses, and incoming
  references recorded by the compiler. It reuses `vos.sailbundle`; it does not
  parse Sail source with another grammar or infer a complete call graph.
- Successful JSON output follows RFC 8259 and a tracked JSON Schema Draft 2020-12
  contract. Results carry the bundle SHA-256, source SHA-256, declaration kind,
  symbol, source location and bounded excerpts. Ordering is deterministic and
  omitted results and truncated excerpts are explicit. Generated entries without
  a local source location are distinguished from searchable local source.
- Each invocation checks every recorded local source digest against current
  bytes. A changed, missing or unreadable owner, malformed bundle or unsafe path
  refuses with a nonzero exit and no partial JSON. The tool reads no source through
  a symbolic link or junction, writes nothing and executes no retrieved text.
  Upstream MD5 fields detect accidental staleness; SHA-256 identifies the bytes
  returned and neither authenticates an untrusted bundle.
- The freshness claim covers the bundle's recorded local owners only. The bundle
  does not identify project selection, new unrecorded files, compiler options or
  the installed library. The interface states this limit. Regeneration and
  `python tools/run.py model bundle --check` remain the compiler comparison; no
  context result establishes successful compilation or behavioral correctness.
- Agent-independent instructions describe a bounded retrieve, edit, typecheck,
  inspect and replan cycle, preserving the ISA profile and requirement contracts.
  Existing model build, property, differential and acceptance gates remain owned
  by their current contracts. Source modules, generated-code packaging and
  compositional verification are assessed separately.
- Focused tests cover emitted declaration shapes and scattered clauses, reference
  locations, ordering and bounds, stale sources with unchanged timestamps,
  malformed inputs and path escape, no partial JSON, and the output schema.
  Real-bundle smoke tests, Python type checks and Windows/Ubuntu Host CI validate
  the integrated tool. The integrator runs the local guest bundle comparison and
  proof gate affected by shared dispatcher registration before final acceptance.

This delivery makes no measured productivity or model-success claim. It changes
no Sail semantics, compiler pin, device behavior or proof-acceptance policy.
