# Fan-out completion contract

`python tools/run.py fanout` owns mechanical local batch completion from explicit
worker handoffs to safe retirement. The integrator owns judgments, conflict
resolution, co-reads and acceptance checks outside the workflows. The user owns
all publication and hosted CI.

## Publication and completion invariant

The [shared ownership rule](../AGENTS.md#worktree-isolation-and-ownership) and
[validation handoff](../AGENTS.md#tool-execution-and-validation) define session
completion on local `main`. `fanout` never pushes, fetches, contacts a remote,
dispatches or queries CI, or polls or waits for Host CI or Guest CI. CI monitoring
requires a separate explicit user instruction. Local completion supplies no hosted
passing evidence.

## Usage

After workers commit their handoffs and stop using their lanes, run from the
checkout holding `main` (use `python3` on Linux). Include a temporary integration
worktree with `--worktree` so its work is merged and its lane is retired too:

```console
python tools/run.py fanout init batch-name --worktree <absolute-worker-path> --cold
python tools/run.py fanout integrate batch-name
python tools/run.py fanout finish batch-name
python tools/run.py fanout status batch-name
```

Repeat `--worktree` for each batch-owned lane. Use `--host-worktree` for a host-owned
checkout whose commits should be integrated but whose checkout and branch remain
with its host. No option discovers or retires unrelated worktrees. An empty lane
list supports an integrator-only batch. `--remote` defaults to `origin` and only
names the local remote tracking ref used for the recommended CI comparison; the
remote need not be configured or reachable. No command updates that ref.
`--full-ci` recommends complete host and guest validation when an item's acceptance
requires it. `--cold` additionally records the need for cold guest installation and
fresh proofs. Use `--defer` repeatedly to retain other acceptance checks.

`init --reading-base COMMIT` names a commit, by its full lowercase SHA, that `main`'s
head descends from at init, such as a revision before the batch's changes. It records
the proof comparison the user should request through Guest CI's `reading_base`
input, as [the Guest CI contract](ci/README.md#inputs-and-execution) describes.
The option is fixed at init. `init` refuses any other value, and `finish` refuses
to settle the reading base itself, since Guest CI accepts only a proper ancestor.
A journal without the field names no reading base.

`integrate` makes ordinary merges so worker ancestry remains decidable. Each merge
subject names the lane branch and its latest non-merge commit subject. Resolve
conflicts and shared edits normally; it never resets a checkout. `finish` includes
integration into local `main` when needed, runs `check --fix`, and requires clean
settled inputs. It freezes the [shared change selection](ci/README.md#change-selection)
against the locally stored `refs/remotes/<remote>/main`, including work committed
before initialization. This ref may be stale; an unavailable comparison selects
full validation. An unchanged resume reuses the frozen selection.

For executable changes, local preparation runs `typecheck`,
`test --only test_lanes` and `test --only test_retained_evidence`, each with a
five-minute limit. Prose-only changes omit those preparation commands. A finding,
crash, timeout or changed checkout stops completion before retirement. The checkout
and revision are rechecked after preparation. These focused checks do not run a
full local suite or replace hosted acceptance.

To commit integrator edits through the tool, pass repeatable `--path <file>` with
`--message <message>` to `finish`. It prints status and selected diffs, stages only
the named files, and includes them in the checker corpus before repair. New UTF-8
files have a text preview; a new file that cannot be decoded as UTF-8 has its byte
count and SHA-256 shown instead. If a repair
changes another file, a required co-read is unresolved, or the index already has
staged changes, resolve that explicitly before resuming. No command performs
co-read blessing or decides that an external acceptance check passed.

`finish` records the settled local revision, retires eligible lanes and returns
success without a hosted verdict. Its output identifies pushes and both CI
workflows as the user's responsibility. `--wait-host` is not supported. `status`
reads only the local journal. Legacy journals retain historical CI records as
read-only evidence; neither pending dispatch intents nor completed records trigger
remote checks or CI actions. A completed legacy journal is bound to its recorded
revision. An unchanged completed batch returns without repeating preparation or
retirement; changed inputs require a new batch.

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

- A batch records its `main` checkout, base revision, advisory remote name,
  explicitly selected worker paths and heads, lifecycle ownership, cold proof
  policy, full-validation policy, reading base or none, comparison base, changed
  paths, recommended checks and deferred acceptance checks. State and evidence
  live under the integration checkout's ignored `out/fanout/` directory.
  Unrelated worktrees are never inferred to be stale from age or a branch name.
- Integration preserves worker ancestry with ordinary Git merges, refuses changed
  handoffs and dirty workers, and stops on conflicts without resetting anything.
  Repair uses the owning checker. Commits stage only explicitly named paths after
  presenting their diffs; unresolved judgments and dirty inputs stop completion.
- Initialization and completion require local `main`, including old completed
  journals. Completion never publishes any ref, reads credentials, contacts remote
  Git or GitHub, dispatches CI, or sleeps to await a hosted run. Host CI and Guest
  CI never gate local retirement. The journal records a local settled revision
  independently of legacy CI evidence, and new batches create no hosted evidence.
- Frozen selection remains advisory and revision-bound. Cold installation, proof
  reading and `--full-ci` recommend every guest lane. A prose-only selection can
  recommend no guest run. Missing comparison history or old journals without a
  full-validation policy retain full validation. No recommendation supplies a
  passing verdict or claims that the user has pushed or dispatched anything.
- Retirement is limited to explicitly batch-owned, clean, integrated worktrees
  under the primary checkout's `.worktrees/`. Host-managed checkouts remain owned
  by their host. Verify resolved containment, branch identity, ancestry and output
  retention before non-forced worktree and branch removal. Preserve useful ignored
  files and native guest outputs outside the retired lane; refuse unsafe paths,
  active output locks and unintegrated branches. Never perform blanket pruning.
- Persist progress atomically, make restart behavior explicit and revalidate inputs
  before resuming consequential steps. Retirement interrupted after removing a
  checkout resumes through its durable receipt. Preserve historical CI evidence
  only for the revision it actually describes. Never interpret pending, skipped,
  canceled or absent hosted checks as passed.

## Acceptance

Focused behavioral tests exercise real temporary Git repositories: integration
and retirement while remote refs remain unchanged, no network/credential/CI calls
or waits, offline initialization and completion, repeat completion, pending and
completed legacy journal resume, changed inputs, partial retirement, local tracking
comparisons and missing-history fallback, full/cold/reading overrides, and refusal
of the old wait option. Preparation findings, timeouts and concurrent input changes
must prevent retirement. Existing dirty-path, containment, branch, ancestry,
retained-output and host-managed preservation controls remain required.
Run focused tests and typecheck during implementation. The user owns the subsequent
push, Host CI and Guest CI; recommend full hosted validation for changes to this
orchestration tool. No local model or proof gate is needed.
