# SPDX-License-Identifier: Apache-2.0
"""Check SPDX license marks across all tracked files (`K-52`, `K-53`).

[COPYRIGHT.md](../../../COPYRIGHT.md) governs Markdown files by path and requires an
`SPDX-License-Identifier` comment at the head of every other authored file:
- `K-52` reads the required SPDX identifier from [COPYRIGHT.md](../../../COPYRIGHT.md)
  and verifies that every file matching `MARKABLE` (outside `REFUSED_TREES`) carries it
  within its first `DEPTH` lines using that file kind's comment syntax. `K-52` is never
  auto-repaired by `--fix` because stamping a license mark asserts authorship/provenance.
- `K-53` checks bidirectional coverage of file kinds: every tracked file kind outside
  `REFUSED_TREES` must appear in `MARKABLE` or `REFUSED`, and every entry in `MARKABLE`
  and `REFUSED` must match at least one tracked file.
"""

import re
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from vos.corpus import UNREAD_PREFIX

if TYPE_CHECKING:
    from . import Context

HEADING = "=== marks: every file that can carry a license mark carries one ==="

LICENSE_MAP = "COPYRIGHT.md"
IDENT_RE = re.compile(r"SPDX-License-Identifier:\s*([A-Za-z0-9.\-+]+)")

# Maximum 1-based line number at which the SPDX comment may appear.
DEPTH = 5

# `(comment_opener, comment_closer)` for each markable file extension or filename.
MARKABLE: dict[str, tuple[str, str]] = {
    ".py": ("# ", ""),
    ".v": ("(* ", " *)"),
    ".ml": ("(* ", " *)"),
    ".ml.in": ("(* ", " *)"),
    ".v.in": ("(* ", " *)"),
    ".lus": ("-- ", ""),
    ".mjs": ("// ", ""),
    ".sh": ("# ", ""),
    ".s": ("# ", ""),
    ".sail": ("// ", ""),
    ".sv": ("// ", ""),
    ".cpp": ("// ", ""),
    ".h": ("// ", ""),
    ".c": ("// ", ""),
    ".rs": ("// ", ""),
    ".toml": ("# ", ""),
    ".editorconfig": ("# ", ""),
    ".txt": ("# ", ""),
    ".cmake": ("# ", ""),
    ".sail_project": ("// ", ""),
    ".yml": ("# ", ""),
    "Dockerfile": ("# ", ""),
}

# File kinds exempt from per-file SPDX marks, with format/ownership rationale.
REFUSED: dict[str, str] = {
    ".md": f"{LICENSE_MAP} governs prose by path, so a per-file mark would restate it",
    ".json": "JSON admits no comment, so a mark would make the file unparseable",
    ".lock": "resolver-generated dependency metadata rather than authored content",
    ".patch": "a unified diff must preserve upstream context and hunk bytes",
    ".gitattributes": "git's own metadata rather than authored content",
    ".gitignore": "git's own metadata rather than authored content",
    ".gitmodules": "git's own metadata rather than authored content",
}

# Directory prefixes exempt from per-file SPDX checks (vendored upstream and verbatim evidence).
REFUSED_TREES: dict[str, str] = {
    UNREAD_PREFIX: "vendored upstream, marked by its own project and left as it arrived",
    "upstream/": "a pinned submodule's own working tree, which is another project",
    "docs/implementation/retained-evidence/": "verbatim copies of recorded native and out/ "
                                              "records, whose citations hash their bytes",
}


def kind_of(path: str) -> str:
    """Return a path's file kind: its `.in` compound suffix, its suffix, or its filename."""
    p = PurePosixPath(path)
    if p.suffix == ".in":
        return "".join(p.suffixes[-2:])
    return p.suffix or p.name


def run(ctx: Context) -> None:
    rep, root = ctx.rep, ctx.root
    rep.line(HEADING)

    ident = IDENT_RE.search(ctx.text(LICENSE_MAP))
    expected = ident.group(1) if ident else ""

    markable: list[str] = []
    unruled: list[str] = []
    seen: set[str] = set()
    for path in ctx.corpus.tracked:
        if path.startswith(tuple(REFUSED_TREES)):
            continue
        kind = kind_of(path)
        seen.add(kind)
        if kind in MARKABLE:
            markable.append(path)
        elif kind not in REFUSED:
            unruled.append(f"{path} is a `{kind}` file, a kind this tool has no ruling "
                           "for: give the kind a comment syntax or a stated refusal")
    ctx.shared["markable"] = markable

    # the mark itself
    faults: list[str] = []
    if not expected:
        faults.append(f"{LICENSE_MAP} states no SPDX identifier, so there is nothing to "
                      "hold these files against")
    else:
        for path in markable:
            fault = _fault(root, path, expected)
            if bool(fault):
                faults.append(fault)
    rep.report("K-52", "file(s) whose license mark is missing or misspelled:", faults,
               f"all {len(markable)} markable files carry `{expected}` in their own "
               "comment syntax")

    # the rulings, both directions
    dead = [f"`{kind}` is {where} and the repository carries no such file; a ruling "
            "nothing exercises is a carve-out nobody audits"
            for table, where in ((MARKABLE, "given a comment syntax"),
                                 (REFUSED, "refused by name"))
            for kind in table if kind not in seen]
    rep.report("K-53", "file kind(s) with no ruling, or a ruling with no file:",
               unruled + dead,
               f"every kind of the {len(ctx.corpus.tracked)} tracked files is ruled on, "
               f"by {len(MARKABLE)} comment syntaxes, {len(REFUSED)} refusals, and "
               f"{len(REFUSED_TREES)} refused trees")
    rep.line()


def _fault(root: Path, path: str, expected: str) -> str | None:
    """What is wrong with one file's mark, or None where nothing is."""
    opener, closer = MARKABLE[kind_of(path)]
    want = f"{opener}SPDX-License-Identifier: {expected}{closer}"
    try:
        text = (root / path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return f"{path}: unreadable, so its mark cannot be decided ({exc})"

    lines = text.splitlines()
    for line in lines[:DEPTH]:
        if line.strip() == want:
            return None

    # It is absent, or it is there and wrong, and those are different repairs.
    found = IDENT_RE.search(text)
    if not found:
        return f"{path}: carries no license mark; its first comment should read `{want}`"
    at = text[:found.start()].count("\n") + 1
    if at > DEPTH:
        return (f"{path}: marked at line {at}, below the opening comment; the mark "
                f"belongs in the first {DEPTH} lines where `{want}` is what is read")
    if found.group(1) != expected:
        return (f"{path}: marked `{found.group(1)}` where {LICENSE_MAP} requires "
                f"`{expected}`")
    return (f"{path}: marks the right license in the wrong syntax; a `{kind_of(path)}` "
            f"file opens a comment as `{opener.strip()}`, so the line should read `{want}`")
