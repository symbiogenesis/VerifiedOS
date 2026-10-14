# Composition-time admission reference

`run.py admission record REQUEST --image IMAGE --graph GRAPH --out RECORD` executes
[AdmissionPath.v](../../proofs/AdmissionPath.v)'s metadata decision over the runtime
members of [the boot roster](../../docs/implementation/contracts/boot-roster.md).
The optional `--roster` selects the boot harness's fixture roster. Offline composer
and admission tools are bound through the roster identity, never certified by
their own output. One refused member refuses the whole generation.

The language is Python under the repository's host-tool policy. This is a
development reference port outside the target trusted computing base. Its
certificate carries recognized judgment, move and facet codes and the bound
artifact digest; those records are metadata, not checked proof terms. An accepted
record always says `scope: fixture-reference` and `production_admission: false`.
Real derivation validation, Tier-0/1 evidence beyond the reference's facet model,
and production refinement remain open. No supplied boolean can close these joins.
The on-device CIC checker remains outside this work.

Requests use this closed JSON shape:

```json
{
  "schema_version": 1,
  "scope": "fixture-reference",
  "profile": "AdmissionPath.demo",
  "members": [
    {
      "member": "rot-firmware",
      "artifact": "relative/path/to/member.bin",
      "tier": 0,
      "certificate": {
        "versions": [4, 2, 1, 3],
        "binds_sha256": "64 lowercase hexadecimal characters",
        "steps": [{"judgment": 2, "move": 0, "facet": 0, "site": 0}]
      }
    }
  ]
}
```

The example is schematic and incomplete: requests must name every runtime member,
in roster order, and cover the requested tier's facets. A missing certificate is
`null` and is refused. Tier assignments and version numbers are explicit fixture
values, not assignments to the real roster. The implementation reads the reference
enums, move routing, phase order and demo requirements from their owner. Requests
cannot override them. Artifact paths stay inside the checkout.

The record hashes exact image, graph, roster, request, artifact, checker and
reference bytes. `validate_record` re-runs the decision and compares the complete
record, refusing changed bytes, altered verdicts and attempts to promote fixture
evidence. Hash binding establishes identity only; it supplies no graph validity,
typing proof, signature or loader authority. The package composer owns graph
validation, and the boot harness owns attaching these records to its image.

`run.py admission emit-reference --out AdmissionComparison.v` generates accepted
and refused equations against the actual Gallina `spec_check`, using every tier,
version field, record deletion, corrupt code, move route, duplicate, reverse and
judgment retagging, plus competing-phase failures. `run.py admission compare`
compiles the reference and generated equations with the configured Rocq compiler
in the guest's native lane and records hashes and process results. This finite
comparison is separate from the proof gate and is not a refinement theorem.
`run.py test --only admission` checks the host behavior, whole-generation refusal,
input boundaries, and image/graph/artifact mismatch handling.

## Production input join

`run.py admission production-record COMPOSITION --projections DIRECTORY --build-record BUILD --image IMAGE --graph GRAPH --out RECORD`
consumes the composer's exact regenerated admission request skeleton and replays
its build record against the published projections, final image, canonical graph
and every runtime artifact. The build checker owns the graph's actual ELF binding.
The record preserves each runtime member, package identity, symbolic artifact
slot, declared tier and derivation source. Exact source, producer, projection,
build-record, checker, image, graph, artifact and derivation bytes are bound and
rechecked before returning or publishing the record. Publication cannot replace
any consumed input, including a hardlinked alias.

This join always emits `scope: production-admission-refusal`, `decision: refused`,
`generation_accepted: false` and `production_admission: false`. Each member names
its remaining blockers and owners: an unassigned tier, an absent derivation,
unaccepted executable roster status where applicable, and the unavailable
production derivation checker. A supplied derivation source binds its bytes only;
even complete fixture metadata cannot supply proof checking, artifact-to-proof
correspondence or Tier-0/1 evidence. The join implements the production input
boundary while the actual checker and real member evidence remain open.

`run.py admission check-production-record RECORD` recomputes the complete refusal
against current inputs. A different image, graph, artifact, derivation, projection,
build record or checker invalidates the saved record. Duplicate JSON fields and
forged success flags refuse. Both commands exit `1` for a current, bound generation
refusal and `2` for malformed, stale or unreadable inputs. Validity of a saved
refusal is separate from generation acceptance.

The focused admission tests use synthetic products and derivation references in
real ELF containers. They check positive identity joins, every absent member's
blockers, stale identities, drift after build validation, protected publication
and refusal replay; they establish no production derivation verdict.
