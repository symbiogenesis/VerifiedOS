# Working rules

*An index, not a second copy. Each rule below is stated in one clause and linked to the artifact that owns it; where the two disagree, the artifact wins. What is here is what bites **before** the file that states it is open.*

## The map

| Artifact | What it is |
| --- | --- |
| [docs/spec.md](docs/spec.md) | The design, and the rationale for the register |
| [docs/requirements-register.md](docs/requirements-register.md) | Normative. The artifact the review gate audits; the prose is its commentary |
| [docs/coverage-matrix.md](docs/coverage-matrix.md) | One cell per property-boundary pair, pointing at the register |
| [docs/implementation-checklist.md](docs/implementation-checklist.md) | Build order, milestones, estimates, and execution state |
| [docs/absence-contract.md](docs/absence-contract.md) | What an auditor searches for and must not find |
| [model/](model/) | The curated Sail model |
| [tools/](tools/) | Every checker and build loop, and [tools/README.md](tools/README.md) states their own rules |
| [THIRD-PARTY.md](THIRD-PARTY.md) | Which upstreams are pinned and which are vendored |

## Before editing a document

- **Derived facts are computed, not copied.** Any count, table, list, or line number some other artifact determines is recomputed by `tools/check.py`, which rewrites the arithmetic under `--fix` and reports the rest. Do not hand-maintain one, and do not add a new one that nothing owns. See [the register's preamble](docs/requirements-register.md#how-to-read-this).
- **Requirement IDs are permanent and order is the prose's.** A retired requirement is struck, never renumbered and never reused; a requirement inserted between two others takes a letter suffix and sits where its obligation belongs, not where its number would put it. Inserting numerically is the natural wrong move.
- **Every register entry carries a criterion**, criterion lines come first, and `· Fail-closed:` and `· RoT-fresh:` confer membership in sets other entries collect. Traces are derived from the entry's own id; spelling one out that the id already derives is a finding.
- **To change a coverage cell, change the register first.** Adding a boundary or a property adds a whole line or column, every cell of which must be filled before the checker passes. See [how to change a cell](docs/coverage-matrix.md#4-how-to-read-a-cell-and-how-to-change-one).
- **Every checklist item carries one estimate cell**, and every subtotal, the grand total, and the progress figures are sums over those cells that `tools/check.py --fix` recomputes. See [checklist conventions](docs/implementation-checklist.md#checklist-conventions).
- **No em-dash (U+2014) in any tracked document**, with no carve-out: rule K-40. A not-applicable cell is `n/a`, never a blank and never a bare dash.
- **The documents carry present-tense current state.** They do not narrate their own past readings or the revisions that got them here; completion evidence on a checked item is the exception, being a measurement recorded at its gate.

## Before incorporating an upstream

**A licence is read at the milestone that would incorporate it, never at release**, and it is the one property whose discovery cannot be repaired downstream. **A vendored tree binds this repository and a pinned submodule does not**, so pinning to read is free and vendoring is a commitment. Terms come from the upstream's own licence file, never inferred from its lineage. See [the plan's §12](docs/implementation-checklist.md#12-build-order-milestones-and-execution-state) and [THIRD-PARTY.md](THIRD-PARTY.md).

## Running the tools

There is no CI in this repository. Nothing runs these but you, by hand, before anything lands.

```console
$ python tools/check.py                       # after any document edit
$ python tools/check.py --fix                 # and rewrite what is arithmetic
$ python tools/check-selftest.py              # after touching the checker itself
$ python tools/typecheck.py                   # after touching any Python

$ wsl -u root -e python3 tools/model.py typecheck
$ wsl -u root -e python3 tools/model.py build
$ wsl -u root -e python3 tools/proof-gate.py
```

The host spells the interpreter `python` and the guest spells it `python3`; neither spelling is portable, and there is no `-d` because `Ubuntu` is WSL's default distribution. `model.py build` logs to a file and writes `ALL_DONE` as its last line, so a caller waits on that marker rather than on a sleep. [tools/README.md](tools/README.md) states why, and the conventions a new tool keeps.

**Adding a rule to the checker is three edits**: the check in its [tools/vos/checks/](tools/vos/checks/) module, its row in [tools/check-rules.md](tools/check-rules.md), and its mutant in [tools/check-selftest.py](tools/check-selftest.py). The tools fail on any one of the three being forgotten.

**The checker's corpus is the git index**, so a new document is invisible to `check.py` until it is tracked, while the selftest's sandbox tracks untracked files too. An untracked `.md` under `docs/` therefore passes the checker and fails the selftest's baseline; keep working notes outside `docs/`.
