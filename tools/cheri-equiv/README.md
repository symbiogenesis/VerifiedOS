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
