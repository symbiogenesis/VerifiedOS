# Copyright and Licensing

Copyright 2026 Edward Miller.

*Three licenses govern this repository, one per kind of content, and every tracked path falls under exactly one of them. Where this document and a license file disagree, the license file wins. [THIRD-PARTY.md](THIRD-PARTY.md) carries everything somebody else wrote and the terms it arrives under.*

## The map

| Path | License | Ground |
| --- | --- | --- |
| Every `.md` file outside `model/`, including [docs/](docs/) and [README.md](README.md) | `CC-BY-4.0`, in [LICENSE-docs.md](LICENSE-docs.md) | The prose is a specification meant to be cited, quoted, and inherited, and a document license says what a software license only gestures at. It is the license the RISC-V specifications themselves carry. |
| Every non-Markdown original file outside `model/`, including [tools/](tools/) and [proofs/](proofs/) | `Apache-2.0`, in [LICENSE.md](LICENSE.md) | The patent grant is the reason rather than a side effect: this repository specifies a bespoke instruction set, a bespoke capability format, and bespoke block instructions, and an implementer of any of them is owed an explicit grant. |
| [model/](model/) | `BSD-2-Clause`, in [model/LICENCE](model/LICENCE) | The curated tree is a derivative of the upstream Sail model and stays on upstream's terms, so a repair found here can go back upstream without a license negotiation. Modifications made here are offered on the same terms. |
| `model/dependencies/` | each component's own, per [THIRD-PARTY.md](THIRD-PARTY.md) | Some components are vendored verbatim with their license files beside them. The rest are `FetchContent` declarations pinned to a content hash: the license file is tracked, the code is not, and it arrives from its own upstream when somebody configures a build. |
| `upstream/` | not redistributed here | Submodule gitlinks: a URL and a commit hash, never the code. What a clone fetches from them answers to its own repository. |
| [LICENSE.md](LICENSE.md), [LICENSE-docs.md](LICENSE-docs.md) | the stewards' own terms | Verbatim license texts. Apache's appendix placeholder is filled in as Apache's own instructions direct; nothing else is changed in either file. |

The split is decidable by path and extension alone, with no per-file judgment: a file is Markdown or it is not, and it is under `model/` or it is not.

## Marking a new file

Every original file whose kind can carry a comment opens with an SPDX line, in that kind's own comment syntax:

```
# SPDX-License-Identifier: Apache-2.0
```

`tools/check.py` reads the identifier out of that block and holds every markable file against it, so a file that arrives unmarked, marked with another identifier, or marked in another kind's comment syntax is a finding. The tool carries a table of comment syntaxes rather than a list of files to skip, so a kind it has no ruling for is a finding too: an unknown kind is a decision somebody owes, not a gap to guess past.

These kinds carry no mark:

| Kind | Ground |
| --- | --- |
| `.md` | The map above already reaches it by path. |
| `.json` | JSON admits no comment, so a mark would make the file unparseable. |
| `.patch` | A diff's bytes are its meaning, and a prepended line breaks the hunks it names. |
| `.gitattributes`, `.gitignore`, `.gitmodules` | Git's own configuration rather than authored content. |

Files under `model/` keep whatever header they arrived with, and a new file authored there takes the upstream BSD-2-Clause header its neighbours carry.

## Terms this tree does not carry

No tracked file is subject to a reciprocal or non-commercial term. That is a property of today's tree rather than a standing guarantee, and the [implementation plan](docs/implementation-checklist.md)'s milestone gates are what preserve it: an upstream's license is read at the milestone that would incorporate it, never at release.

Three planned upstreams carry terms that would decide what the composed system could be licensed as, and all three calls are taken without moving a row of the map. The verified compiler and the control-plane compiler are **contained**: each is a build-time producer this repository never redistributes, so its non-commercial term reaches nothing offered here. The kernel specification is **authored instead**: no `GPL-2.0-only` object is translated, that being the one term of the three that would have reached the shipped image, and a derivation once written is not undone by a later decision. [THIRD-PARTY.md](THIRD-PARTY.md) quotes each instrument, and what containment costs is recorded at the milestones that spend it.

The no-copyleft property is the *tree*'s and not every build artifact's: the golden-model emulator links against GMP, offered as `LGPL-3.0-or-later OR GPL-2.0-or-later`, which makes that executable a Combined Work whose conditions attach on conveyance. [THIRD-PARTY.md](THIRD-PARTY.md) states what those conditions are and when they would be engaged.
