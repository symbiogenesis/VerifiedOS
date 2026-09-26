# Reference compiler component comparison

This contract resolves M1.2f's component-route question, F-456, under the
[reference build's lowering discipline](../implementation-checklist.md#0-the-discipline-two-languages-two-golden-models).
It selects the existing GC-free CompCert-C route for the staged endpoint IPC
component. The C is authored against Gallina and compiled through the contained
purecap backend. It is not extracted from Gallina. The comparison supplies finite
functional evidence; source refinement, secure compilation, target timing and
production admission retain their existing owners.

## Inputs and observations

[EndpointIPC.v](../../../proofs/EndpointIPC.v) owns the component semantics.
[ipc_oracle.v](../../../tools/wasm-oracle/ipc_oracle.v) owns the ordered check
population. [ipc_oracle.c](../../../tools/wasm-oracle/ipc_oracle.c) is its explicit
array-and-loop implementation under the [scalar source-value contract](compiler-source-values.md).
Each check must have one corresponding position in both outputs. A count copied
from an earlier run is not the population's owner.

The host arm freshly stages the Gallina source closure and compiles it with
CertiRocq to Wasm. The target arm preprocesses and compiles the C source closure
with the contained compiler, assembles and composes its output, and executes it
on the Sail emulator. Both arms expose the complete ordered Boolean vector and
its first failing position, using zero for no failure. A successful process that
omits a coordinate, emits a non-Boolean value, truncates output or disagrees on
the first failure is refused. Aggregate true/false agreement alone is insufficient.

The generated observation wrappers may expose existing checks and serialize their
answers. They may not replace a check with its expected result or transplant one
implementation into the other. The finite correspondence review reads the
representation of inductives, lists, function arguments and recursion, and each
check family's mapping between the independent implementations.

## Qualification

Acceptance requires the following evidence on one source-bound population:

- Fresh positive executions agree at every position, with the expected nonempty
  population and successful process exits.
- The existing semantic mask-boundary mutation produces the same nonempty failing
  set and first failure in both arms. Comparing either mutated arm to the pristine
  peer refuses agreement.
- Generated single-position output corruptions are refused at every position.
  Missing, extra, reordered and malformed observations have explicit refusals.
  These are comparator controls, not implementation mutation kills.
- The report binds source and generated-wrapper bytes, check population,
  preprocessed C, compiler settings and executable, Wasm bytes, image, emulator,
  model-source identity, profile and command results. It binds the Wasm producer's
  package export, compiler/prover/runtime identities and staging inputs. Missing or
  changed dependencies, outputs or producer identities invalidate reuse.
- A repeatable command regenerates both arms and compares them. Reading an old
  module after a source change cannot qualify the component.

The [oracle environment](../../../tools/wasm-oracle/README.md#pinned-environment)
remains the intended reproducible installation. The existing installed legacy
environment may supply a separately identified comparison if its exact package
export, tools, complete staged sources and fresh output identities are retained.
This takes F-452's producer-binding alternative. It does not complete the intended
environment's bootstrap, supply its missing lockfile, or qualify a portable
installation. The report must distinguish those claims.

## Handoff and limits

An accepted comparison establishes the reference-only authored-C arm of M1.2f.
The generated program campaign, actual-local narrowing census, composition-bound
source populations and complete backend join remain required at their existing
owners. No component report alone closes M1.2f, M1.7 or a downstream boot item.

Host CI checks the changed tools on Windows and Ubuntu. The integrator dispatches
both Guest CI lanes for the settled revision and records their pending status
without waiting. This Wasm/compiler/Sail comparison is a separate acceptance
experiment outside the Guest CI workflow; dispatch cannot substitute for its
recorded execution.
