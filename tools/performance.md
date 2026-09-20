# Tool performance acceptance

Performance maintenance preserves the decisions owned by the
[checker registry](check-rules.md) and the
[proof evidence contract](README.md#current-evidence-and-generated-documentation).
The requirements register, authored citations and proof sources remain their
respective owners. Sharing their parsed representations must not create another
authored statement of the same fact.

## Scope and acceptance

This maintenance batch covers proof source analysis, host document checking and
validation orchestration. Its starting revision is
`62a39d76b4946638043d5d780b0759d9241f99aa`.

An optimization is accepted only when all applicable conditions hold:

1. The old and new implementation produce equal decisions and diagnostics on the
   same inputs. Focused tests cover malformed inputs and the changed algorithm's
   boundaries, including edits between calls when parsing is reused.
2. A parse cache belongs to an explicit immutable input or one run. A path,
   timestamp or file size alone cannot authorize reuse after an edit. Failed or
   unsupported parses cannot become successful cached verdicts.
3. Proof dependency order, witness checks, assumption audits, content validation
   and the joint kernel check retain their existing meanings. A changed proof
   gate receives its applicable native regression checks; cached portable
   evidence cannot replace them.
4. Mutation sandboxes remain independent. Every selected case runs, failures
   remain failures, and reporting order stays deterministic. Worker reuse must
   not preserve mutations or uncontrolled process state between cases.
5. Measurements identify the revision, input scope, interpreter, command,
   repetitions and worker count. Compare equivalent work on the same machine;
   record component time separately from end-to-end time. Accept a repeatable
   improvement in the changed path without a material end-to-end regression.
   Timing noise is not a test failure or a speedup claim.
6. The integrated tree passes `python tools/run.py --check --tests`. New
   deliverables are tracked before validation. The integrator owns generated
   repairs, shared documentation and the final stable-tree wave.

The proof lane owns source-analysis machinery and its consumers; the checker
lane owns document/checker parsing; the runner lane owns sandbox and worker
orchestration. Their focused tests and measurements precede integration. A
dependency, persistent cache or trust-boundary change needs an explicit rationale
and tests for its additional failure modes before it joins this batch.

## Library and concurrency choices

The project already pins Astral's uv, Ruff and ty in
[pyproject.toml](pyproject.toml). Retain the locked environment and optimize
repeated work before adding another dependency.

Python 3.14's [executor API](https://docs.python.org/3.14/library/concurrent.futures.html)
offers bounded submission through `map(buffersize=...)` and isolated interpreter
workers. Interpreter workers still serialize arguments and results and import
their own modules; choose them only after measuring the actual workload and
preserving its isolation contract.

[Path.info](https://docs.python.org/3.14/library/pathlib.html#pathlib.Path.info)
can reuse directory-entry metadata. Such metadata can accelerate enumeration,
but it cannot establish proof-input freshness. The proof gate's content hashes
remain authoritative.

Astral documents [uv's shared cache](https://docs.astral.sh/uv/concepts/cache/)
as safe for concurrent uv operations. Each worktree still owns its installed
environment; sharing the download cache does not authorize sharing mutable
environments or proof outputs.
