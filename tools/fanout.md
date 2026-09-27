# Fan-out completion contract

`python tools/run.py fanout` owns mechanical batch completion from explicit worker
handoffs to hosted validation and retirement. The integrator owns judgments,
conflict resolution, co-reads and acceptance checks outside the workflows.

## Required behavior

- A batch records its integration checkout, base revision, publication remote and
  branch, explicitly selected worker paths and heads, lifecycle ownership, cold
  proof policy and deferred acceptance checks. State and evidence live under the
  integration checkout's ignored `out/fanout/` directory. Unrelated worktrees are
  never inferred to be stale from age or a branch name.
- Integration preserves worker ancestry with ordinary Git merges, refuses changed
  handoffs and dirty workers, and stops on conflicts without resetting anything.
  Repair uses the owning checker. Commits stage only explicitly named paths after
  presenting their diffs; unresolved judgments and dirty inputs stop publication.
- Publication pushes a settled commit without force. Host CI must pass on both
  Windows and Ubuntu for that exact revision. Start Host CI when no suitable run
  exists. Pending, failed, skipped or canceled checks supply no passing evidence.
- After Host CI passes, dispatch Guest CI with both model and proofs lanes for the
  same revision, forwarding the explicit cold policy. Record run identifiers or
  URLs, revisions and available statuses. Never poll or wait for a guest verdict.
  Interrupted or ambiguous dispatches must not silently duplicate a guest run.
- Retirement is limited to explicitly batch-owned, clean, integrated worktrees
  under the primary checkout's `.worktrees/`. Host-managed checkouts remain owned
  by their host. Verify resolved containment, branch identity, ancestry and output
  retention before non-forced worktree and branch removal. Preserve useful ignored
  files and native guest outputs outside the retired lane; refuse unsafe paths,
  active output locks and unintegrated branches. Never perform blanket pruning.
- Persist progress atomically, make restart behavior explicit and revalidate inputs
  before resuming consequential steps. A changed integration revision needs fresh
  hosted evidence. Completion may record Guest CI as pending, never as passed.

## Acceptance

Focused behavioral tests exercise real temporary Git repositories and mocked
GitHub responses: successful integration and retirement, dirty and escaping paths,
unmerged or moved branches, retained outputs, host-managed preservation, wrong
revision or incomplete Host CI evidence, failed dispatch and interrupted resume.
Run focused tests and typecheck during implementation, then require hosted Host CI
and dispatch both Guest CI lanes for the settled revision. Workflow edits require
actionlint. No local model or proof gate is needed for this orchestration tool.
