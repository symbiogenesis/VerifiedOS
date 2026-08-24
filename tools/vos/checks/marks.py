# SPDX-License-Identifier: Apache-2.0
"""marks: the license mark every file that can carry one carries.

[COPYRIGHT.md](../../../COPYRIGHT.md) governs Markdown by path and every other
original file by a mark in the file itself. The first half is closed by having no
per-file fact to drift. The second is a claim about every markable file in the tree
that nothing held: a new source file arrives unmarked and reads exactly like a marked
one, because the mark's whole job is to be there when somebody later asks a question
nobody is asking today. How many such files there are is this group's `ok` line to
state and is deliberately not written down anywhere here, the count being exactly the
kind of fact the tool exists to keep out of prose.

**The identifier is read from the map rather than restated here.** Every marked file
repeating `Apache-2.0` is one more copy of a sentence COPYRIGHT.md owns, so this
group takes the identifier out of that document and holds the files against it. Change
the map and the files are wrong; change the files and they are wrong; the two cannot
quietly disagree.

**A kind is markable or refused, and there is no third answer.** The obvious shape for
this rule is a list of files to skip, and it is the wrong one: a skip list is a proviso
that must itself be audited, and the day a new file kind lands is the day it is
silently outside the rule. So the tool carries a table of comment syntaxes rather than
a list of exceptions, and a kind in neither table is a finding that names the kind and
asks for a decision. Refusals are refusals of *format*, not of importance: JSON admits
no comment at all, so a mark in one is not a mark but a corruption. Markdown is refused
for the opposite reason, that the map already reaches it by path.

Both directions are held, as the conferral rules elsewhere hold theirs. A file kind no
ruling covers is a gap; a ruling no file exercises is a carve-out nobody audits, and it
goes when the last file of its kind does.

What this cannot decide is whether the mark is *true*. A file marked Apache-2.0 that
was pasted from somewhere else is marked wrongly and reads green here, which is the
same residue every other group in this tool declares: the mark is checked for presence
and spelling, and its provenance is a person's to know.

**Which is why `--fix` does not write the mark**, though it is the most mechanical
repair in this tool and the finding already prints the line to paste. Everything
`--fix` rewrites is recomputed from an artifact the repository already carries: a count
from the thing counted, a total from its items, the value determined before the flag is
passed and only transcribed by it. A mark is not that. Prepending one asserts that the
file is this project's own work, which nothing in the tree determines, and an unmarked
file is the single visible sign that something arrived from outside. `--fix` is run to
repair arithmetic, so a marking side effect would stamp a provenance claim on a pasted
file while somebody was fixing a checklist total, turning the one case this rule can
detect into a false claim. Rewriting a mark that is present and wrong would be worse
still, overwriting a license statement somebody made on purpose. The line is cheap to
paste and the decision behind it is not, so the decision stays with a person.
"""

import re
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from vos.corpus import UNREAD_PREFIX

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== marks: every file that can carry a license mark carries one ==="

# the document that owns the identifier, so this module never spells it
LICENSE_MAP = "COPYRIGHT.md"
IDENT_RE = re.compile(r"SPDX-License-Identifier:\s*([A-Za-z0-9.\-+]+)")

# A mark below the opening comment is not what a reader or a scanner finds first, so
# the mark is required in the head of the file rather than merely somewhere in it. Five
# lines is a shebang, a mark, and room to spare.
DEPTH = 5

# Every kind that can carry a comment, and how that kind opens and closes one. Adding a
# file kind to the repository means adding its row here, which is the point: the rule
# refuses to guess.
MARKABLE: dict[str, tuple[str, str]] = {
    ".py": ("# ", ""),
    ".v": ("(* ", " *)"),
    ".mjs": ("// ", ""),
    ".s": ("# ", ""),
    ".toml": ("# ", ""),
    "Dockerfile": ("# ", ""),
}

# Every kind that is not marked, each with the reason it is not. A reason of *format*
# is the only kind admitted here: the JSON entry would be corrupted by a mark, and
# Markdown is reached by the map instead.
REFUSED: dict[str, str] = {
    ".md": f"{LICENSE_MAP} governs prose by path, so a per-file mark would restate it",
    ".json": "JSON admits no comment, so a mark would make the file unparseable",
    ".gitattributes": "git's own metadata rather than authored content",
    ".gitignore": "git's own metadata rather than authored content",
    ".gitmodules": "git's own metadata rather than authored content",
}

# The trees refused whole rather than by kind, because what is foreign is the tree and
# not any kind inside it. `model/` is the corpus's own exclusion, imported rather than
# respelled so the two cannot come to disagree about which tree is not this
# repository's. `upstream/` is ordinarily invisible here, its entries being gitlinks
# rather than files, but a submodule that is checked out is a working tree full of
# somebody else's sources and this rule has no business marking them.
#
# Trees are not held to K-53's other direction. A kind's ruling is a carve-out that
# earns its place by covering something, where a tree is a structural fact about the
# repository that is no less true on the day it happens to be empty.
REFUSED_TREES: dict[str, str] = {
    UNREAD_PREFIX: "vendored upstream, marked by its own project and left as it arrived",
    "upstream/": "a pinned submodule's own working tree, which is another project",
}


def kind_of(path: str) -> str:
    """A path's kind: its extension, or its whole name where it has none. A dotfile
    has no extension by this reading, which is what puts `.gitignore` in the table
    under its own name rather than under an extension it shares with nothing."""
    p = PurePosixPath(path)
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
            if fault:
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
