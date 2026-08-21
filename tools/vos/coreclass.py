# SPDX-License-Identifier: Apache-2.0
"""The core-class table, read out of every artifact that writes it.

Four artifacts write the same table. Three of them are prose, each stating a class's
vector geometry in its own idiom, and the fourth is the composition the model is
actually built from. Nothing held the four together: a class table is exactly the
shape where a figure edited in one document renders correctly in all four, because
each site reads as an independent statement rather than as a copy.

Counts sit differently and are read here anyway. R-15-113 calls them composition
parameters rather than architecture, so a *machine* may carry any roster; what this
repository carries is one composed machine, and the reference instantiation the
specification states is a claim about that machine. A count stated in prose that no
roster realizes is a figure nobody renders wrong.

Everything here is a parse and never a decision, as everywhere else in this package.
What the sites mean and which of them may disagree is `vos/checks/counts.py`'s.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config

CONFIG = "model/config/verifiedos.json"

# The five classes, in the order the model's own enumeration declares them
# (model/model/core/core_class.sail). The spelling here is the documents',
# lowercased for the configuration and prefixed for the roster's class token.
CLASSES = ("C", "V", "M", "S", "RoT")

# Both prose tables key their rows on the bolded class name, and only the
# specification writes the `-class` suffix, so one pattern reads both. A second
# row for one class means the table has grown a shape this rule cannot read,
# which is reported rather than resolved by picking one.
ROW_RE = re.compile(r"(?m)^\| \*\*(C|V|M|S|RoT)(?:-class)?\*\* \|(.*)$")

# The register states the same table as one sentence rather than as rows.
REG_SEG_RE = re.compile(r"(?:(C|V|M|S)-class|the (RoT)) \(([^)]*)\)")

VLEN_RE = re.compile(r"VLEN=(\d+)")
# The multiplication sign the count column is written with, spelled as its codepoint
# rather than as itself: the glyph is one ruff refuses in a string on the ground that
# it is indistinguishable from a Latin `x`, which is exactly why the documents use it
# and exactly why this pattern must not be read as containing one.
COUNT_RE = re.compile(r"\u00d7(\d+)")


@dataclass
class CoreClasses:
    """Every site's answer, keyed by what the site is rather than where it is."""

    # site -> {class -> VLEN in bits, zero where the site states the class is
    # vectorless}; a site whose table this rule can no longer read maps to None
    stated: dict[str, dict[str, int] | None] = field(default_factory=dict)
    # the reference instantiation's counts, which only the specification states
    counts: dict[str, int] = field(default_factory=dict)
    # the composition's own two statements: the class table and the roster
    declared: dict[str, int] | None = None
    roster: dict[str, int] | None = None


def _table(text: str, cell: int) -> dict[str, int] | None:
    """One prose table's class-to-VLEN map, or None where its shape has moved.

    `cell` is which column after the class name carries the datapath, because the
    specification's table has a count column between them and the profile's does not.
    """
    found: dict[str, int] = {}
    for m in ROW_RE.finditer(text):
        name = m.group(1)
        if name in found:
            return None
        cells = m.group(2).split("|")
        if len(cells) <= cell:
            return None
        vlen = VLEN_RE.search(cells[cell])
        found[name] = int(vlen.group(1)) if vlen else 0
    return found if set(found) == set(CLASSES) else None


def _counts(text: str) -> dict[str, int]:
    """The specification's count column, summed per row. A row states its count as
    one figure or as a sum of pinned and unpinned parts, and both are the class's
    count; nothing else in the row is read, because a datapath geometry written
    `32x32` carries the same multiplication sign the counts do."""
    found: dict[str, int] = {}
    for m in ROW_RE.finditer(text):
        cells = m.group(2).split("|")
        if not cells:
            continue
        total = sum(int(n) for n in COUNT_RE.findall(cells[0]))
        if total:
            found[m.group(1)] = total
    return found


def _register(body: str) -> dict[str, int] | None:
    found: dict[str, int] = {}
    for m in REG_SEG_RE.finditer(body):
        name = m.group(1) or m.group(2)
        if name in found:
            return None
        vlen = VLEN_RE.search(m.group(3))
        found[name] = int(vlen.group(1)) if vlen else 0
    return found if set(found) == set(CLASSES) else None


def _composition(root: Path) -> tuple[dict[str, int] | None, dict[str, int] | None]:
    """The composition's class table and roster. Either answers None where the
    configuration no longer carries it in the shape the model reads, which is a
    finding the caller words rather than an exception it has to catch."""
    path = root / CONFIG
    table = config.value(path, "platform", "core_classes")
    entries = config.value(path, "platform", "core_roster")

    declared: dict[str, int] | None = {}
    if isinstance(table, dict):
        for name in CLASSES:
            row = table.get(name.lower())
            exp = row.get("vlen_exp") if isinstance(row, dict) else None
            if not isinstance(exp, int) or isinstance(exp, bool):
                declared = None
                break
            declared[name] = (1 << exp) if exp else 0
    else:
        declared = None

    roster: dict[str, int] | None = None
    if isinstance(entries, list):
        roster = dict.fromkeys(CLASSES, 0)
        for entry in entries:
            token = entry.get("class") if isinstance(entry, dict) else None
            name = token.removeprefix("CoreClass_") if isinstance(token, str) else ""
            if name not in roster:
                roster = None
                break
            roster[name] += 1
    return declared, roster


def read(root: Path, register_body: str) -> CoreClasses:
    """One pass over the four sites. A file that is not there yields an unreadable
    site rather than raising, for the reason the geometry parse does the same."""
    cc = CoreClasses()

    def text(rel: str) -> str:
        path = root / rel
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    spec = text("docs/spec.md")
    cc.stated["the specification's core-class table"] = _table(spec, 1)
    cc.stated["the profile's core-class table"] = _table(
        text("docs/isa-profile.md"), 0)
    cc.stated["the register's class enumeration"] = _register(register_body)
    cc.counts = _counts(spec)
    cc.declared, cc.roster = _composition(root)
    return cc
