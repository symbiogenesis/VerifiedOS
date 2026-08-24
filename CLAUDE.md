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
| [rtl/](rtl/) | The RTL this repository authored, and the record binding each claimed absence to a build |
| [tools/](tools/) | Every checker and build loop, and [tools/README.md](tools/README.md) states their own rules |
| [THIRD-PARTY.md](THIRD-PARTY.md) | Which upstreams are pinned and which are vendored |

## Before editing a document

- **Derived facts are computed, not copied.** Any count, table, list, or line number some other artifact determines is recomputed by `tools/check.py`, which rewrites the arithmetic under `--fix` and reports the rest. Do not hand-maintain one, and do not add a new one that nothing owns. See [the register's preamble](docs/requirements-register.md#how-to-read-this).
- **Requirement IDs are permanent and order is the prose's.** A retired requirement is struck, never renumbered and never reused; a requirement inserted between two others takes a letter suffix and sits where its obligation belongs, not where its number would put it. Inserting numerically is the natural wrong move.
- **Every register entry carries a criterion**, criterion lines come first, and `· Fail-closed:` and `· RoT-fresh:` confer membership in sets other entries collect. Traces are derived from the entry's own id; spelling one out that the id already derives is a finding. A criterion clause is admitted where it decides and not where it is short, so one that decides nothing is deleted or made to decide, never moved into the prose the gate does not audit.
- **An entry and the prose it cites are read together.** Editing either side leaves that pair owed a re-reading, which rule K-61 reports; `tools/co-read.py --show <id>` prints the two sides against each other and `--bless <id>` records the reading. Blessing is a judgment and deliberately not `--fix`, so a stale pair cannot be cleared by repairing arithmetic. A prose edit dirties a median of four pairs.
- **To change a coverage cell, change the register first.** Adding a boundary or a property adds a whole line or column, every cell of which must be filled before the checker passes. See [how to change a cell](docs/coverage-matrix.md#4-how-to-read-a-cell-and-how-to-change-one).
- **Every checklist item carries one estimate cell**, and every subtotal, the grand total, and the progress figures are sums over those cells that `tools/check.py --fix` recomputes. See [checklist conventions](docs/implementation-checklist.md#checklist-conventions).
- **No em-dash (U+2014) in any tracked document**, with no carve-out: rule K-40. A not-applicable cell is `n/a`, never a blank and never a bare dash.
- **The documents carry present-tense current state.** They do not narrate their own past readings or the revisions that got them here; completion evidence on a checked item is the exception, being a measurement recorded at its gate.
- **A `§n` is resolved by hand.** Rule K-13 holds only that some document in the repository numbers that section, because the numbering is shared, so a reference aimed at the wrong document passes green. Bare `§n` names [the register](docs/requirements-register.md)'s section, or [the profile](docs/isa-profile.md)'s where the sentence says the profile states it; [the version matrix](docs/cheri-version-matrix.md) is where both conventions meet and states its own reading.
- **Nothing is argued against an invented opposition.** A scare-quoted slogan no source in the corpus says has no referent, so the comparison cannot be made precise. A framing sentence that resists two rewrites is deleted rather than rewritten a third time.
- **The README addresses a newcomer.** No bare `§n` in it: cite by a hyperlink whose text names the thing. Mechanism lives in its inventory tables and in the spec, so an inaccurate highlight is repaired with a more precise short word and never by appending a clause.

## Before incorporating an upstream

**A licence is read at the milestone that would incorporate it, never at release**, and it is the one property whose discovery cannot be repaired downstream. **A vendored tree binds this repository and a pinned submodule does not**, so pinning to read is free and vendoring is a commitment. Terms come from the upstream's own licence file, never inferred from its lineage. See [the plan's §12](docs/implementation-checklist.md#12-build-order-milestones-and-execution-state) and [THIRD-PARTY.md](THIRD-PARTY.md).

## Before editing the model tree

**[model/](model/) is `-text` in [.gitattributes](.gitattributes)**, so git stores its line endings verbatim instead of normalizing them, and any tool that writes CRLF rewrites every line of the file it touched. Two do it silently: PowerShell's `Set-Content -Value <array>`, where the fix is `[System.IO.File]::WriteAllText` or `-NoNewline` on a `-Raw` string, and a plain `git archive` when vendoring, which honours `core.autocrlf` and so wants `git -c core.autocrlf=false archive`. The tree is vendored byte-identically from its upstream pin, so a swept file hides the real diff of a curation batch and breaks the line counts that batch reports as its evidence. After any scripted edit, check `git diff --stat` against the number of lines the edit meant to touch.

## Before editing the RTL tree

**[rtl/](rtl/) holds only files this repository authored**, and an imported core is reached through its gitlink under `upstream/` rather than copied in. It takes the repository's default line endings and **not** `model/`'s verbatim rule, for the reason stated at that rule in [.gitattributes](.gitattributes): there is no upstream here to stay byte-identical to. **A synthesis parameter is stated twice on purpose**, once in [the provenance record](rtl/synthesis-provenance.md) with the absence it removes and once in the configuration package as a literal at its field, and rule K-76 holds the two together with the absence contract; changing one alone is a finding, which is what makes the record a binding rather than a description.

## Running the tools

There is no CI in this repository. Nothing runs these but you, by hand, before anything lands.

```console
$ python tools/gate.py                        # the three host gates, in one run
$ python tools/gate.py --fix                  # and rewrite what is arithmetic first
$ python tools/check.py                       # one gate alone, after a document edit
$ python tools/check-selftest.py              # one alone, after touching the checker
$ python tools/typecheck.py                   # one alone, after touching any Python
$ python tools/co-read.py --show R-15-073c    # a pair K-61 says is owed a reading
$ python tools/test.py                        # after changing what any tool does
$ python tools/rtl.py provenance              # the absences, and what binds each

$ wsl -u root -e python3 tools/rtl.py lint    # the authored RTL, alone
$ wsl -u root -e python3 tools/rtl.py elaborate --background
$ wsl -u root -e python3 tools/rtl.py wait    # and the module set it removed
$ wsl -u root -e python3 tools/model.py typecheck
$ wsl -u root -e python3 tools/model.py build
$ wsl -u root -e python3 tools/proof-gate.py
```

`gate.py` is the three host gates as one run and one exit code, and they share it because all three only read the checkout; under `--fix` the repair runs alone and first, the selftest copying the working tree as it starts. The host spells the interpreter `python` and the guest spells it `python3`; neither spelling is portable, and there is no `-d` because `Ubuntu` is WSL's default distribution. `model.py build` logs to a file and writes `ALL_DONE` as its last line, so a caller waits on that marker rather than on a sleep. [tools/README.md](tools/README.md) states why, and the conventions a new tool keeps.

**Adding a rule to the checker is three edits**: the check in its [tools/vos/checks/](tools/vos/checks/) module, its row in [tools/check-rules.md](tools/check-rules.md), and its mutant in [tools/check-selftest.py](tools/check-selftest.py). The tools fail on any one of the three being forgotten.

**The checker's corpus is the git index**, so a new document is invisible to `check.py` until it is tracked, while the selftest's sandbox tracks untracked files too. An untracked `.md` under `docs/` therefore passes the checker and fails the selftest's baseline; keep working notes outside `docs/`.
