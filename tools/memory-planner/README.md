# Optional planner adapters

[interfaces.json](interfaces.json) pins the upstream boundaries and records the
licenses read before integration. This directory contains authored adapter code;
it vendors no upstream code. These are standalone host integrations and do not
admit a new dependency into the VerifiedOS production toolchain.

## MiniMalloc

With the pinned MiniMalloc Python package available and `tools` on Python's
import path, an existing problem and solver can be wrapped directly:

```python
import minimalloc as mm
from vos.memory_planner_adapters import MiniMallocSolver

checked = MiniMallocSolver(mm, mm.Solver(), work_budget=10000)
solution = checked.solve(problem)
evidence = checked.last_evidence
```

The ordinary value is the upstream `Solution`, or `None`. Buffer order, fixed
offsets, positive integer alignment, inactive gaps, and half-open lifetimes are
preserved. Signed times are translated without changing overlap; overflow is
refused. Hints remain advisory. Spatial gap windows return `None` with diagnostics
because their partial spatial occupancy has no admitted conversion. The wrapper
targets the pinned Python fields, not a C++ ABI or every `Solver` control method.
The caller supplies the installed MiniMalloc build; its compiled binary is not
authenticated by the Python wrapper.

`minimalloc_from_csv(text, mm, capacity)` accepts the pinned columns, including
`buffer_id`, `start`, inclusive `end`, alignment, hints, gaps, and fixed offsets.
`minimalloc_to_csv(original_text, solution)` preserves every input column and
appends or replaces the offsets. Unknown columns, malformed records, and endpoint
overflow are refused. Capacity is supplied separately, as it is upstream.

The baseline runs on a separate problem object before bounded extra search. An
invalid baseline, exception, or timeout never returns a purportedly checked
solution. Baseline timeout controls remain the baseline solver's configuration;
`work_budget` bounds the additional core search.

## ExecuTorch

The optional factory checks the installed `exir/memory_planning.py` source hash
against the exact commit in the manifest before exposing the suite callback:

```python
from executorch.exir.memory_planning import MemoryPlanningAlgorithmSuite
from vos.memory_planner_adapters import executorch_algorithm

checked = executorch_algorithm(work_budget=10000)
suite = MemoryPlanningAlgorithmSuite(algo_list=[checked])
```

Use this suite at the pinned compiler's memory planning boundary. Its algorithm
callback consumes `(alignment, specs, graph_module, graph_signature, extra_padding)`
and returns the actual `MemoryAlgoResult` with `spec_dict` and `bufsizes`. The
suite applies the chosen decisions; the callback leaves those writes to it.

The supplied spec set determines input, output, and mutable-buffer policy.
The adapter preserves its identities, bounded shapes, per-pool assignments,
reserved input prefixes, and extra padding. It retains a checked greedy baseline
and enforces componentwise pool non-regression. A separate semantic snapshot
prevents a mutating baseline from changing the model that the checker validates.
Current `mem_offset` values are previous outputs, as in the upstream algorithm;
they do not introduce fixed-location constraints.

Direct storage-backed views preserve their root and relative offset. External
roots, chained views, concurrent overlapping sibling views, incomplete lifetimes,
and unbounded shapes are explicitly unsupported. View-aware collection and
input/output policy remain the pinned frontend's responsibility. Errors raise
`UnsupportedAdapterError` and retain `last_evidence`; the legacy callback has no
non-success return structure. The source hash does not attest dependencies or
prove export/runtime compatibility.

## TFLite Micro

```console
python tools/run.py memory-planner demo-tflm
```

The guest demo downloads only the pinned, SHA-256-checked header closure and
license to its native build lane. It compiles the authored
[CheckedOfflinePlanner](tflm_checked_plan.h) against the real
`MicroMemoryPlanner` header and executes [the demonstration](tflm_demo.cpp).
No header stubs establish this result.

The replacement consumes immutable host-planned rows in `AddBuffer` order. It
checks sizes, inclusive endpoints, alignment, bounds, coexistence, fixed offsets,
and preservation mode before exposing offsets. It uses no heap or initialization
scratch. Rows must outlive the planner. `ready()` supplies admission status
separately from the legacy size result; callers must check statuses. A mismatched
registration invalidates the planner, and `Init` does not revive an invalid plan.

The example compares a 32-byte reusable arena with a constructed 48-byte separate
reservation and checks malformed plans. It is a planner-boundary demonstration;
it runs no model inference and measures neither persistent runtime memory nor
whole-device footprint. Host Python tests use explicitly identified contract
fixtures for MiniMalloc and ExecuTorch. Installed-framework export and runtime
qualification are separate from those tests.
