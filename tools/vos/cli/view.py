#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Weave the specification and requirements register into a generated reading view.

    tools/run.py view                 # writes out/spec-woven.md
    tools/run.py view --out PATH      # writes to an ignored or external path

Renders [docs/spec.md](../../../docs/spec.md) verbatim with each entry from
[docs/requirements-register.md](../../../docs/requirements-register.md) quoted beneath
its citing bookmark ([vos/coread.py](../coread.py)).
"""

import argparse
import re
import subprocess
from pathlib import Path

from vos import coread
from vos import corpus as corpus_mod
from vos.corpus import ANCHOR_RE, PROSE, Corpus
from vos.register import REGISTER, REQ_ID_PATTERN, read_register

BANNER = (
    "*A generated reading view, never a source: the specification's prose with each "
    "register entry rendered beneath the bookmark that cites it. Derived by "
    "`tools/run.py view` from [spec.md](../docs/spec.md) and "
    "[requirements-register.md](../docs/requirements-register.md); edit those and "
    "regenerate.*"
)

_ENTRY_LEAD_RE = re.compile(rf"^\*\*({REQ_ID_PATTERN})\*\* ")


def _entry_blocks(corpus: Corpus, ids: set[str]) -> dict[str, list[str]]:
    """Return each requirement entry's contiguous register lines as blockquote lines."""
    doc = corpus.by_name[REGISTER]
    out: dict[str, list[str]] = {}
    i = 0
    while i < len(doc.lines):
        m = _ENTRY_LEAD_RE.match(doc.lines[i])
        if m and m.group(1) in ids and m.group(1) not in out:
            block: list[str] = []
            j = i
            while j < len(doc.lines) and doc.lines[j]:
                block.append("> " + doc.lines[j])
                j += 1
            out[m.group(1)] = block
            i = j
        else:
            i += 1
    return out


def weave(corpus: Corpus) -> tuple[list[str], int, list[str]]:
    """The woven lines, how many entries were placed, and any entry left homeless."""
    reg = read_register(corpus)
    spec = corpus.by_name[PROSE]
    blocks = _entry_blocks(corpus, reg.id_set)
    marks = coread.bookmarks(corpus, reg)

    home: dict[str, list[str]] = {}      # bookmark -> entries rendered beneath it
    repeats: dict[str, list[str]] = {}   # bookmark -> entries it cites again
    homeless: list[str] = []
    for ident in reg.ids:
        targets = marks.get(ident, [])
        if not targets or ident not in blocks:
            homeless.append(ident)
            continue
        base = "r" + ident[1:].lower()
        anchor = base if base in targets else targets[0]
        home.setdefault(anchor, []).append(ident)
        for other in targets:
            if other != anchor:
                repeats.setdefault(other, []).append(ident)

    # every unfenced anchor, in order of appearance on its line
    at: dict[int, list[str]] = {}
    for m in ANCHOR_RE.finditer(spec.raw):
        i = spec.line_of(m.start())
        if not spec.fenced[i]:
            at.setdefault(i, []).append(m.group(1))

    lines: list[str] = [BANNER, ""]
    placed = 0
    for i, line in enumerate(spec.lines):
        lines.append(line)
        for anchor in at.get(i, ()):
            for ident in home.get(anchor, ()):
                lines.append("")
                lines.extend(blocks[ident])
                placed += 1
            cited = repeats.get(anchor, ())
            if cited:
                # direction-neutral on purpose: a -n repeat may precede its base
                # bookmark in the prose (r-12-035-2 does), so "above" would misdirect
                lines.append("")
                lines.append("> ↳ cited here again: " + ", ".join(cited)
                             + ", stated in full at their own bookmarks.")
    if homeless:
        lines += ["", "## Entries no bookmark places", ""]
        for ident in homeless:
            lines.append("")
            lines.extend(blocks.get(ident, [f"> **{ident}** (block unreadable)"]))
    return lines, placed, homeless


def _output_path(root: Path, name: str | None) -> Path:
    """Keep derived output outside source files, including in nested checkouts."""
    base = root.resolve()
    requested = Path(name) if bool(name) else Path("out/spec-woven.md")
    path = (requested if requested.is_absolute() else base / requested).resolve()
    owners = [parent for parent in path.parents if (parent / ".git").exists()]
    if path.is_relative_to(base) and base not in owners:
        owners.append(base)
    for owner in owners:
        relative = path.relative_to(owner).as_posix()
        result = subprocess.run(["git", "-C", str(owner), "check-ignore", "--quiet", "--", relative],
                                cwd=owner, env=corpus_mod._git_environment(owner),
                                capture_output=True, text=True, check=False, timeout=30)
        if result.returncode == 1:
            raise ValueError(f"output inside the repository must be ignored and untracked: {relative}")
        if result.returncode != 0:
            raise ValueError(f"cannot establish an ignored output path: {result.stderr.strip()}")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        suggest_on_error=True, description="Weave the specification and the register into one reading view.")
    parser.add_argument("--out", metavar="PATH",
                        help="external or ignored repository-relative output (default: out/spec-woven.md)")
    args = parser.parse_args(argv)

    try:
        root = corpus_mod.find_root()
        out_path = _output_path(root, args.out)
        corpus = corpus_mod.load(root)
        lines, placed, homeless = weave(corpus)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"FAIL view: {error}")
        return 1

    print(f"wove {placed} entries into the prose -> {out_path}")
    if homeless:
        print(f"{len(homeless)} entries reach no bookmark and are appended at the "
              f"end: {', '.join(homeless)}")
    return 0

