# Portable proof assistance

## Delivery contract

This bounded tool-maintenance delivery adapts local example retrieval and bounded
repair from [RocqStar](https://arxiv.org/html/2505.22846v2) and the
[LLM4Rocq workflow](https://github.com/LLM4Rocq/rocq-skills/tree/11cbe8807e6e572530bd56905e65b6861ec47dd3).
It adds a source-navigation command and instructions any shell-capable agent can
follow. It imports no upstream implementation, model, service or Python package.
The existing proof gate remains the sole automated proof-acceptance route.

Implementation begins after this contract is committed. Its acceptance predicate is:

- `python tools/run.py proof-search` searches local Rocq declarations and their
  proof scripts by query words, optional tactic words and authored requirement
  citations. Ranking and tie-breaking are deterministic. A caller can exclude a
  target source from example retrieval.
- Each result includes a repository-relative source path, one-based location,
  declaration name, source SHA-256, authored requirement references and a bounded
  source excerpt. Incomplete, admitted and aborted scripts are distinguished from
  lexically closed ones; no result claims that a theorem was checked.
- The command reads the current working-tree proof sources on every invocation,
  including new local proof files. It persists no search index or prover state,
  executes no retrieved text, uses no network and writes no proof source or receipt.
  Malformed input and unreadable sources produce a nonzero exit and a diagnostic.
- Machine output is UTF-8 [RFC 8259 JSON](https://www.rfc-editor.org/rfc/rfc8259),
  described by a tracked [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12)
  schema. Human output and `--help` work without a particular editor, agent,
  provider account or installed protocol server. The implementation uses the
  existing Python tool environment and no added dependencies.
- Focused tests cover ranking and exclusion, comments and strings, script status,
  fresh reads after edits/additions/deletions, bounded output, input errors and the
  JSON contract. Windows and Ubuntu Host CI validate the settled implementation.
  No Gallina, gate input, theorem statement or accepted assumption is changed.

This delivery makes no proof-success-rate or time-saving claim. It does not reopen
or complete Q19a, Q19b, Q19c or Q20b. A live protocol adapter, learned retrieval or
multi-agent proof planner requires its own scoped qualification and cost comparison
under the [proof qualification contract](proof-qualification-contract.md).

## Acceptance boundary

R-05-018 makes synthesis an untrusted finder. R-05-018a requires fresh acceptance
over the exact source and dependency environment; R-05-163 fixes each theorem's
allowed assumptions. A search hit, lexical `Qed`, empty displayed goal list or a
source hash supplies none of those checks. Hashes identify retrieved source bytes,
not a dependency closure or a checked environment. Requirement citations describe
what a file discusses, not what a retrieved declaration discharges.

Freeze the intended theorem statement, executable definitions and allowed
assumptions before repairing a proof. A necessary contract change returns to its
requirement owner for review; it is not a successful proof repair. R-05-166's
inhabitation and distinguishing rejected examples remain required, together with
the requirement-to-contract review. Never use an upstream verifier's general
allowlist of classical axioms in place of the repository's exact assumption audit.
