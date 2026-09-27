# Fan-out completion contract

`python tools/run.py fanout` owns mechanical batch completion from explicit worker
handoffs to hosted validation and retirement. The integrator owns judgments,
conflict resolution, co-reads and acceptance checks outside the workflows.

## Publication and completion invariant

All session work must reach local `main` and remote `main` before completion.
Worker and integration worktrees are temporary local isolation only. Run batch
completion from the checkout holding `main`, selecting any temporary integration
worktree as a worker to merge and retire. Only `refs/heads/main` may be published;
never push a work branch or create a publication tag. Old non-main journals cannot
authorize completion: initialize a new batch on `main` instead.

Both workflows dispatch from `main` with an explicit settled revision input, so
checkout stays pinned even if another session advances the remote branch. Require
that revision to be on remote `main` before dispatch, bind hosted evidence to the
checked-out revision, and refuse a changed local integration revision. Completion
requires all selected owned handoffs to be merged into `main`, published, validated
by Host CI, handed to both Guest CI lanes, and retired with their outputs retained.
Tests must demonstrate refusal off `main`, publication of only `main`, rejection of
old branch/tag journals, exact-revision dispatch and preserved retirement behavior.

## Usage

After workers commit their handoffs and stop using their lanes, run from the
checkout holding `main` (use `python3` on Linux). Include a temporary integration
worktree with `--worktree` so its work is merged and its lane is retired too:

```console
python tools/run.py fanout init batch-name --worktree <absolute-worker-path> --cold
python tools/run.py fanout integrate batch-name
python tools/run.py fanout finish batch-name --wait-host 1800
python tools/run.py fanout status batch-name
```

Repeat `--worktree` for each batch-owned lane. Use `--host-worktree` for a host-owned
checkout whose commits should be integrated but whose checkout and branch remain
with its host. No option discovers or retires unrelated worktrees. An empty lane
list supports CI handoff for an integrator-only batch. `--remote` defaults to
`origin`; publication always targets `main`. Use
`--defer` repeatedly to retain acceptance checks outside the hosted workflows.

`integrate` makes ordinary merges so worker ancestry remains decidable. Resolve
conflicts and shared edits normally; it never resets a checkout. `finish` includes
integration into `main` when needed, runs `check --fix`, requires clean settled
inputs, and pushes only `main` without force. CI dispatches on `main` with the exact
commit as its revision input. Authentication uses the configured GitHub credentials;
the REST client reads `GH_TOKEN`, then `GITHUB_TOKEN`, then the noninteractive Git
credential helper. It needs Actions read/write access as well as Git push access.
The GitHub CLI is not required, and credentials never enter the journal.
Run identifiers and tested commits remain in the journal as evidence references.
Retirement removes local worker branches; the tool never creates remote work
branches or publication tags. Preexisting remote refs need explicit cleanup.

To commit integrator edits through the tool, pass repeatable `--path <file>` with
`--message <message>` to `finish`. It prints status and selected diffs, stages only
the named files, and includes them in the checker corpus before repair. If a repair
changes another file, a required co-read is unresolved, or the index already has
staged changes, resolve that explicitly before resuming. No command performs
co-read blessing or decides that an external acceptance check passed.

Without `--wait-host`, `finish` returns a finding with pending Host CI and the
resume command. `--wait-host SECONDS` bounds host-only polling (maximum 7200);
expiration leaves the journal resumable. Failure or cancellation stops completion.
Guest dispatch records its identifier, tested revision and pending status, then
retirement runs without waiting for a guest verdict. `status` reads only the local
journal. An ambiguous interrupted dispatch retains its intent and uses the unique
workflow token to recover identity; it never silently submits a duplicate.

The journal is `out/fanout/<batch>/state.json`. Retained checkout outputs live under
that batch's `retained/` directory; native guest outputs stay on their native
filesystem under the build root's `fanout-retained/` directory. Retirement records
the destinations. Known log layouts and companion receipts are retained together.
Ambiguous shared logs and unknown legacy layouts stay in place and are listed as
deferred retention; the command does not guess their owner. Host output retention
uses same-filesystem renames and refuses cross-volume moves. Failed retention or
unsafe cleanup leaves a resumable refusal.
Keep the worker stopped throughout integration and retirement. Host-managed lanes,
dirty or unintegrated work, unexpected branch changes and unrelated lanes survive.
When a completed batch's integration revision changes, initialize a new batch.

## Required behavior

- A batch records its `main` checkout, base revision, publication remote and
  `main` branch, explicitly selected worker paths and heads, lifecycle ownership, cold
  proof policy and deferred acceptance checks. State and evidence live under the
  integration checkout's ignored `out/fanout/` directory. Unrelated worktrees are
  never inferred to be stale from age or a branch name.
- Integration preserves worker ancestry with ordinary Git merges, refuses changed
  handoffs and dirty workers, and stops on conflicts without resetting anything.
  Repair uses the owning checker. Commits stage only explicitly named paths after
  presenting their diffs; unresolved judgments and dirty inputs stop publication.
- Publication pushes a settled commit only to `main`, without force or tags.
  Initialization and completion refuse a work branch, including old completed
  journals. Host CI must pass on both
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
