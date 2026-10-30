# Capability-format vector campaign

`python tools/run.py rtl vectors` compiles the curated Sail capability sources
with a generated probe harness and writes the model's answers into the checkout's
native guest lane. `python tools/run.py rtl crosscheck` generates those vectors,
builds the independent [SystemVerilog consumer](vos_cheri_vectors_tb.sv), and
compares its answers line for line.

## Source owners

[Typed probe declarations](../vos/rtl_vectors.py) own the function signatures,
model calls and printed fields. They use the shared [oracle emitter](../vos/oracle.py)
for fixed-width formatting, the deterministic shift register and probe printing.
[The authored campaign](campaign.sail) owns the capability-specific helpers and
ordered sweep schedule. The generated harness lives under the native lane's
`cheri-equiv` directory; it is never an authored repository input.

The schedule retains exhaustive bounds encodings and permission masks, deliberate
narrowing corners, movement and representability cases, and malformed inputs.
Seed state continues across the same subcampaigns, and related probe calls keep
their original interleaving. Each data line carries its kind, inputs and outputs
as fixed-width lowercase fields. The SystemVerilog consumer parses and reformats
the inputs before computing its answer, so a misparse can cause a disagreement.
An unknown vector kind refuses the comparison.

Decode records derive their tag from the decoded bounds: malformed encodings are
untagged. This preserves the model's tagged-length precondition while exercising
the complete encoding domain, including representations unreachable with a tag.

The generic [capability oracle spec](../oracle-specs/capformat.json) retains its
own input population. Shared emission does not make that sampled population a
replacement for this campaign's exhaustive domains and deliberate corners.

## Validation boundary

Focused host controls exercise generated probe signatures and fields, deterministic
emission, malformed declarations and generation failures. The migration comparison
binds an immutable pre-migration generator, both source closures, per-kind vector
populations and complete ordered output digests. Equal population counts alone
cannot establish equal inputs, seed transitions or output order.

Hosted RTL acceptance runs the generated campaign against the independent
consumer under the [Guest CI contract](../ci/README.md). The
[tooling retirement plan](../../PLAN.md#coverage-preserving-tooling-retirement)
owns remaining acceptance and the conditional prover-workaround retirement.
This consolidation supplies no new model/RTL equivalence theorem or measured
performance improvement.

## Migration evidence

The [hosted comparison](https://github.com/symbiogenesis/VerifiedOS/actions/runs/41008675464)
passed on 2026-10-30. Both generators compiled against the same unchanged model
source bytes and produced identical complete ordered data streams. The comparison
controls detected altered, truncated, reordered and whitespace-changed data while
allowing commentary changes.

[Hosted migration comparison](../../docs/implementation/retained-evidence/tooling-retirement-20261030/manifest.json),
SHA256 `d46b1664cb90fa170bd87c967bdb29013b3bdf7a37dddb1f8080b7ac5b7adebf`,
binds the verbatim report, comparison helper, temporary workflow, output log and
run identity. The report owns source revisions, tool identities, populations and
digests. The helper and workflow are historical reproduction inputs at their
recorded candidate revision; the active tool suite retains neither.

The `retire-tools-20261030-final` fanout journal owns final-revision Host CI and Guest
CI dispatch evidence. The separate hosted RTL crosscheck keeps its independent
acceptance boundary.
