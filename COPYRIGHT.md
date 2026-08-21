# Copyright and Licensing

Copyright 2026 Edward Miller.

*Three licenses govern this repository, one per kind of content, and every tracked path falls under exactly one of them. Where this document and a license file disagree, the license file wins and this document is defective. The [third-party inventory](THIRD-PARTY.md) carries the vendored components and their own terms.*

## The map

| Path | License | Ground |
| --- | --- | --- |
| Every `.md` file outside `model/`, including [docs/](docs/) and [README.md](README.md) | **CC BY 4.0**, in [LICENSE-docs.md](LICENSE-docs.md) | The prose is a specification meant to be cited, quoted, and inherited, and a document license says what a software license only gestures at. It is the license the RISC-V specifications themselves carry. |
| Every non-Markdown original file, including [tools/](tools/) and [proofs/](proofs/) | **Apache-2.0**, in [LICENSE.md](LICENSE.md) | The patent grant is the reason rather than a side effect: this repository specifies a bespoke instruction set, a bespoke capability format, and bespoke block instructions, and an implementer of any of them is owed an explicit grant that a bare attribution license leaves silent. |
| [model/](model/) | **BSD-2-Clause**, in [model/LICENCE](model/LICENCE) | The curated tree is a derivative of the upstream Sail model and stays under the upstream license, so a repair found here can go back upstream without a license negotiation. Modifications made in this repository are offered under the same BSD-2-Clause terms. |
| `model/dependencies/` | each component's own, per [THIRD-PARTY.md](THIRD-PARTY.md) | Vendored verbatim, each with its license file beside it, none of them modified. |
| `upstream/` | not redistributed here | These are submodule gitlinks: a URL and a commit hash, never the code. What a clone fetches from them answers to its own repository. |
| [LICENSE.md](LICENSE.md), [LICENSE-docs.md](LICENSE-docs.md) | the stewards' own terms | Verbatim license texts, reproduced unmodified. Apache's appendix placeholder is filled in as Apache's own instructions direct; nothing else is changed in either file. |

The split is decidable by path and extension alone, with no residue and no per-file judgment: a file is Markdown or it is not, and it is under `model/` or it is not.

## Marking a new file

Every non-Markdown original file carries an SPDX line as its first comment, in the file's own comment syntax:

```
# SPDX-License-Identifier: Apache-2.0
```

Markdown files carry none: the map above governs them by path, and a per-file marking on three megabytes of prose would be three thousand restatements of one fact. Files under `model/` keep whatever header they arrived with, and a new file authored there takes the upstream BSD-2-Clause header its neighbours carry.

## What licensing decides that is still open

Three planned dependencies carry terms that constrain what the composed system may be licensed as, and each is booked in the [implementation plan](docs/implementation-checklist.md) at the milestone that would incorporate it, ahead of the work rather than after it. **Two of the three foreclose options rather than merely complicating them**, and both were read at their pins rather than inferred from lineage. The compiler provenance is under a non-commercial license, which is not an open-source license and cannot ship under anything on this page. The kernel-specification provenance is GPL-2.0-only, which Apache-2.0 cannot be combined with, so a kernel derived from it would carry that term instead. The [third-party inventory](THIRD-PARTY.md) decomposes both; neither is a paperwork question, and neither has an answer that is free.

Nothing currently tracked in this repository carries a copyleft or non-commercial term. That is a property of today's tree, not a standing guarantee, and it is what the milestone gates exist to preserve.
