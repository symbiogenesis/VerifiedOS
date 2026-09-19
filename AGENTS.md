# Working rules

Read [README.md](README.md) first for the project's purpose, design goals, and current status.

AGENTS.md owns shared agent instructions. Edit shared rules here. The linked artifacts own the detailed contracts summarized below; check them before changing the relevant area and resolve disagreements at their source.

## Repository map

| Artifact | Purpose |
| --- | --- |
| [docs/README.md](docs/README.md) | Document index by subject |
| [docs/spec.md](docs/spec.md) | Design and rationale |
| [docs/requirements-register.md](docs/requirements-register.md) | Normative obligations audited by the review gate |
| [docs/assurance/coverage-matrix.md](docs/assurance/coverage-matrix.md) | Property-boundary coverage traced to the register |
| [docs/implementation/implementation-checklist.md](docs/implementation/implementation-checklist.md) | Build order, acceptance predicates, estimates, and execution state |
| [docs/implementation/completion-log.md](docs/implementation/completion-log.md) | Recorded landing evidence |
| [docs/hardware/absence-contract.md](docs/hardware/absence-contract.md) | Hardware structures the audit must not find |
| [model/](model/) | Curated Sail model |
| [rtl/](rtl/) | Authored RTL and synthesis provenance |
| [proofs/](proofs/) | Gallina sources and proof metadata |
| [tools/README.md](tools/README.md) | Commands, toolchain, validation, and tool-development rules |
| [THIRD-PARTY.md](THIRD-PARTY.md) | Upstream licenses and incorporation status |

## Before editing a document

- **Generate derived facts from their owner.** Do not hand-maintain counts, tables, lists, or line numbers determined by another artifact. Use the owning generator; `tools/check.py --fix` repairs the derived artifacts it supports and reports other disagreements. New derived views need generation and checking. See the [register preamble](docs/requirements-register.md#how-to-read-this) and [checklist conventions](docs/implementation/implementation-checklist.md#checklist-conventions).
- **Keep requirement IDs permanent and entries in prose order.** Strike retired requirements without renumbering or reusing IDs. Use a letter suffix for an insertion between existing requirements. Follow the [register's entry format](docs/requirements-register.md#how-to-read-this): acceptance criteria first, then applicable `· Fail-closed:`, `· RoT-fresh:`, and `· Trace:` lines. Fail-closed and freshness declarations determine membership in their collected sets. Prose bookmarks derive from the requirement ID; spell out only non-default prose citations.
- **Keep each obligation decidable from its entry.** Every criterion must contribute to the decision. Delete or make testable a clause that does not; do not move required decision detail into prose to shorten the register.
- **Re-read changed entry/prose pairs.** K-61 reports pairs whose contents changed. Use `python tools/run.py coread --show <id>`, read both sides, and then `python tools/run.py coread --bless <id>` to record agreement. Blessing requires judgment and is never an arithmetic repair.
- **Change the register before changing coverage.** A new property or boundary requires every new property-boundary cell to be filled. See [coverage maintenance](docs/assurance/coverage-matrix.md#4-how-to-read-a-cell-and-how-to-change-one).
- **Keep estimates and landing evidence in their assigned places.** Each estimated item has one estimate cell; a parent whose children carry the estimates has none. Let the checker repair totals and percentages. Landed or struck items have one [completion-log](docs/implementation/completion-log.md) entry with the exact checklist label. A landed checklist item keeps its header, cell, one summary line, and log link; open-item notes stay in the checklist. Follow the [checklist conventions](docs/implementation/implementation-checklist.md#checklist-conventions).
- **Use current-state prose.** Avoid revision narratives outside recorded completion evidence. No em-dash (U+2014) in any tracked text file, including code and comments (K-40). Write `n/a` for a not-applicable cell, never a blank or bare dash.
- **Verify section references by reading their targets.** K-13 only checks that some heading carries the number. In the register, a bare `§n` names its section; follow each other document's stated convention, including the [version matrix's](docs/hardware/cheri-version-matrix.md). In README.md, use descriptive links instead of bare section numbers, keep highlights concise, and put mechanism in the inventory tables or specification.
- **Make comparisons against sourced claims.** Remove invented opponents and unsupported slogans. Delete a framing sentence that resists two clear rewrites.
- **Fold outside critiques into their owners.** Check each disposition against the register, put the judgment in [the critique](docs/background/critique.md) with the plan item that answers it, and put resulting work in the plan's Q-series. Once incorporated, remove the root working note.

## Before incorporating an upstream

Read the selected revision's own license files at the milestone that would incorporate it. Record the intended use and distribution in [THIRD-PARTY.md](THIRD-PARTY.md), following [the project's licensing rules](COPYRIGHT.md#terms-this-tree-does-not-carry). Do not infer terms from a project's lineage or treat a pin as permission to copy its source.

Use `git ls-files -s upstream` to inspect tracked pins: mode `160000` identifies a gitlink, not vendored files. Inspect vendored and fetched dependencies separately. A linked worktree's uninitialized submodule status does not establish that the repository lacks the pin.

## Before editing the model or RTL

- **Preserve model bytes outside the intended edit.** [model/](model/) is a modified upstream derivative; [.gitattributes](.gitattributes) sets `model/** -text -eol`, so Git stores its line endings verbatim. Write UTF-8 with LF; avoid PowerShell array writes that introduce CRLF. Use absolute paths with `[System.IO.File]` APIs, whose relative paths follow the process directory rather than `Set-Location`. When vendoring, use `git -c core.autocrlf=false archive`. After scripted edits, inspect `git diff --stat` and `git ls-files --eol -- model` for unintended rewrites.
- **Keep imported RTL in its upstream repository.** [rtl/](rtl/) holds authored files and uses the repository's LF text rules; imported cores are reached through gitlinks under `upstream/`.
- **Update synthesis bindings together.** A setting named by [synthesis provenance](rtl/synthesis-provenance.md) must match the configuration package's literal and the [absence contract](docs/hardware/absence-contract.md). K-76 checks that relation; preserve it when changing a setting or claimed absence.

## Worktree isolation and ownership

**Every fan-out subagent needs its own dedicated Git worktree**, including read-only scouts, reviewers, document workers, and nested agents. Only the integrator writes the integration checkout. Follow the [isolation procedure](tools/README.md#worktree-isolation-during-fan-out):

1. The parent provisions lanes serially with `python tools/run.py worktree create <unique-lane> --base <revision> --json`. Repository-created lanes live under the primary checkout's ignored `.worktrees/` directory and require a fresh branch and destination. A host-provisioned worktree may keep its location after `python tools/run.py worktree verify <absolute-worktree> --base <revision> --json`; add `--exact` for an unchanged starting revision, and review any descendant commits or uncommitted changes separately. Check the guide's Git prerequisites and do not dispatch without verified isolation.
2. The brief names the absolute worktree path, branch or detached HEAD, base revision, owned files, focused checks, and integrator. Name `lane_root` from the JSON for guest work. Uncommitted integration edits are absent from the base; commit needed inputs first or explicitly transfer and record them. Implementation starts only after the item's [contract and acceptance predicate](docs/implementation/implementation-checklist.md#checklist-conventions) are landed; unrelated work may proceed.
3. The worker verifies `git -C <worktree> rev-parse --show-toplevel`. Every shell call sets that worktree as its working directory; Git calls use `git -C <worktree>`, and file tools and scripted writes use absolute paths rooted in that checkout. Build and log outputs belong to that lane. Report writes outside it to the integrator. Coordinate shared mutable toolchain state separately.
4. Retire only batch-owned lanes whose work is integrated. Inspect their status, preserve needed outputs, and verify commit containment in the integration revision. Record guest paths before unregistering, then use `git worktree remove` and `git branch -d`. Delete only uncited outputs belonging to the retired lane. Never force removal, reset a branch to reuse its name, or remove another session's checkout; host-managed cleanup belongs to the host.

For the Windows/WSL workflow, create lanes and inspect checkout state on Windows. Guest tools read sources through `/mnt/<drive>` and keep build trees, caches, and scratch under their native lane in `/root/build`, with logs under `/root/logs`. Do not redirect guest scratch to the checkout, a Windows mount, or `/tmp`, or place a checkout on `\\wsl.localhost`. Intentional exports and tracked generated artifacts use their commands' documented destinations. Wait for builds and read their logs through `run.py model wait` or `run.py rtl wait`; use the command's completion verdict rather than polling a success marker. `python tools/run.py model lane` prints placement; `python tools/run.py provision` checks it. See [filesystem placement](tools/README.md#where-a-file-lives-and-which-lane-touches-it).

**Inspect hunks before staging by path; never use `git add -A`.** Run `git status --short` and `git diff -- <path>` before staging. Investigate unexpected paths and leave another session's hunks to their owner, even inside a file you edited. The integrator owns shared instructions, arithmetic repair, and the final gate for the settled batch.

## Running and changing tools

Use `python tools/run.py <command>` on Windows; it dispatches toolchain commands into WSL. On Linux, including the WSL guest, use `python3 tools/run.py <command>` directly. `python tools/run.py help` lists commands and `python tools/run.py <command> --help` gives their options. Read [the tool guide](tools/README.md) before changing Python tools or their configuration.

**A sandboxed Windows shell can report installed tools as missing.** If `git`, `python` or `uv` is not recognized, inspect command resolution and installation-path access before installing replacements or switching shells. This host's Git resolves through the user's WinGet Links directory and Python/uv through the user's Python installation; sandbox access restrictions can hide both. Use the execution tool's normal escalation mechanism when required, and re-check resolution in that context. See [host tool discovery](tools/README.md#host-tool-discovery).

**Batch edits and match checks to the changed surface.** Follow the [check schedule](tools/README.md#check-scheduling-during-fan-out). Read-only scouts run no gates. Workers run focused checks and report drift and deferred work; they do not run `--fix` or bare `run.py`. Keep one full host wave active across the machine by default, including all worktrees.

| Purpose | Command |
| --- | --- |
| Feedback after a document batch | `python tools/run.py check` (or `python tools/check.py`) |
| Changed checker rule | `python tools/run.py selftest --rule <rule-id>` |
| Changed tool behavior | `python tools/run.py test --only <module-substring>` |
| Python feedback before integration | `python tools/run.py typecheck` |
| Integrator's final host wave | `python tools/run.py --check` |
| Repair followed by a fresh host wave | `python tools/run.py --fix` |
| CI-equivalent host validation | `python tools/run.py --check --tests` |

The host wave runs the checker, mutation selftest, and typecheck. Bare `run.py` runs the same default wave read-only. `--check` leaves source artifacts unchanged, though bootstrap may populate ignored environments and caches. `--fix` repairs supported derived artifacts before validation; `--tests` adds the default behavioral suite. K-110 checks that AGENTS.md is tracked as the nonempty UTF-8 shared instruction source.

Append `--tests` for tool changes or CI-equivalent validation. Before the final wave, settle authored changes, track new deliverables by path, resolve co-reads and known findings, and finish all writes. A red checker baseline must be resolved before selftesting. Keep the checkout stable while gates read it. Record the command, tested revision and uncommitted input scope, verdict, and deferred checks. Repeat only when changed inputs or unresolved findings invalidate evidence. [CI](.github/workflows/host-gates.yml) runs host validation, with a `--summary` path that names the member that went red and adds no gate, on Windows and Ubuntu; required slow tests and guest measurements remain separate acceptance work under the [landing conventions](docs/implementation/implementation-checklist.md#checklist-conventions).

- **Add a checker rule with its registry row and mutant.** Update the appropriate [check module](tools/vos/checks/), [rule registry](tools/check-rules.md), and [selftest](tools/vos/cli/selftest.py). Enumeration readers also need the applicable floor or documented fail-closed treatment. See [adding a rule](tools/README.md#adding-a-rule-to-the-checker).
- **Generate validation where an oracle exists.** Use `oracle`, `seed`, and `quickchick` as described in [the generator guide](tools/README.md#the-three-generators-and-what-each-answers). Distinguish stillborn mutants (did not compile), killed mutants (detected), and survivors (not detected); compilation failures are not kills, and survival needs investigation.
- **Reserve the checkout exclusively for `seed properties`.** It temporarily mutates `model/` in place. No other reader, writer, gate, or staging operation may use that checkout for the entire run, including another window. Investigate unexpected capability-format or selftest-baseline failures for an overlapping mutation run.
- **Account for corpus membership.** The checker reads working-tree contents of indexed files; new documents are invisible until tracked. The selftest also copies non-ignored untracked files, so its baseline can differ. Keep scratch notes in ignored output directories and track intended deliverables before final validation.
