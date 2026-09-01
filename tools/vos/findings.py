# SPDX-License-Identifier: Apache-2.0
"""The findings register, and the plan's own count of what it indexes.

Two artifacts, one relation. `docs/implementation-checklist.md` records a finding in
a completion note, under a count with its bullets beneath it or as a bullet that
opens `Finding`; `docs/findings-register.md` gives that finding an id, a type, the
item that raised it, and a disposition. This module reads both sides and states
where they disagree, so that the rule over them and any later tool asking the same
question share one parse rather than two.

**The block's size is its bullets and never its own word.** A note writes `Six
findings.` above six of them, and holding the register against that word would let a
note that lies about itself carry a register that agrees with the lie. So the size is
counted from the bullets and the word is held against the count, which is the
ordinary arithmetic-is-recomputed discipline applied to a document's own enumeration.

**A leading word that is not a count is prose and not a malformed block.** One note
opens a paragraph `Environment findings, booked for later lanes.` and carries three
findings inside it; the plan states them in prose rather than under a count, so the
register indexes them by hand and marks them `in prose`. Reading that bullet as a
block this parse could not count would make a permanent finding out of a shape the
register already declares it does not hold. What keeps the reading fail-closed
instead is the comparison itself: a count word this alternation stops recognizing
takes its whole block out of the plan's side, and the entries indexing it are then
entries naming findings the note no longer records, which is a finding either way.

The register's own template is fenced, and a fence displays text rather than
declaring anything, so the fenced spans are dropped before either pattern runs. That
is the same rule `vos/corpus.py` states for every document the checker reads, applied
here because this parse takes text rather than a `Document`.
"""

import re
from dataclasses import dataclass, field

from vos import figures

REGISTER = "docs/findings-register.md"
PLAN = "docs/implementation-checklist.md"

# The closed vocabularies. A type says what a reader does with the finding and a
# disposition says whether anything is owed; an entry carrying neither in the words
# the register declares is an entry this parse cannot place, which is a finding rather
# than an entry quietly dropped from the comparison.
TYPES = ("owed-act", "upstream-defect", "method", "measurement")
DISPOSITIONS = ("open", "closed", "standing")

_FENCE_RE = re.compile(r"[^\S\r\n]*```")

# An entry head, and the three property lines under it. The head's id is three digits
# with an optional letter, which is what makes the register's fenced `F-nnn` template
# unreadable as an entry even before the fence is dropped.
_ENTRY_RE = re.compile(r"^\*\*(?P<id>F-\d{3}[a-z]?)\*\* (?P<kind>[a-z-]+): (?P<what>\S.*)$")
_PROP_RE = re.compile(r"^· (?P<name>Raised|Disposition|Restates): (?P<value>\S.*)$")
_RAISED_RE = re.compile(r"^(?P<item>[^,]+?)(?P<prose>, in prose)?$")
_STATE_RE = re.compile(r"^(?P<state>[a-z-]+)")

# The count words a note spells its blocks with, capitalized as a note writes them.
# The table is `vos.figures`'s own word form rather than a second list, because the two
# are the same convention: a note states a count in words and this reads it back, so a
# hand-kept table here is a copy free to stop where the convention does not. It stops
# where that one stops, at ninety-nine, past which a document states digits.
_COUNTS = {figures.words(n).capitalize(): n for n in range(1, 100)}

# A checklist item, checked, unchecked, or struck. The label runs to the first middot,
# which is where the plan separates an item's id from its name; an item with no middot
# at all is its own label, `Initial check/emit/FAST tooling` being the one such.
_ITEM_RE = re.compile(r"^[^\S\r\n]*\* (?:\[[ x]\] |~~)\*\*(?P<label>[^*\r\n]+?)\*\*")
# Longest first, so `Twenty-three` is read as itself rather than as a `Twenty` whose
# alternative then fails on the hyphen and takes the block out of the reading with it.
_BLOCK_RE = re.compile(r"^(?P<ind>[^\S\r\n]*)\* \*{0,2}(?P<word>"
                       + "|".join(sorted(_COUNTS, key=len, reverse=True))
                       + r") findings\b")
_SINGLE_RE = re.compile(r"^(?P<ind>[^\S\r\n]*)\* \*{0,2}Finding[,:]")
_BULLET_RE = re.compile(r"^(?P<ind>[^\S\r\n]*)\* ")


@dataclass(frozen=True)
class Entry:
    """One register entry, as the document states it."""

    ident: str
    kind: str
    raised: str
    in_prose: bool
    disposition: str
    restates: str
    line: int


@dataclass
class Index:
    """The findings register: whether it is there at all, and what it carries."""

    present: bool = False
    entries: list[Entry] = field(default_factory=list)
    malformed: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Block:
    """One findings block of a completion note: whose it is, how many bullets it
    carries, and what its own word claims. `declared` is zero for the singleton form,
    which states no count and carries exactly the one finding its bullet is."""

    item: str
    line: int
    size: int
    declared: int


@dataclass
class Plan:
    """The checklist's side: every item label it carries, and every findings block."""

    present: bool = False
    items: set[str] = field(default_factory=set)
    blocks: list[Block] = field(default_factory=list)


def _unfenced(text: str) -> list[str]:
    """The document's lines with every fenced span blanked.

    Blanked rather than removed, so that a line number is the document's own and a
    finding sends a reader to the line the register writes.
    """
    lines = text.split("\n")
    inside = False
    for i, line in enumerate(lines):
        marker = "```" in line and _FENCE_RE.match(line) is not None
        if marker or inside:
            lines[i] = ""
        if marker:
            inside = not inside
    return lines


def parse(text: str) -> Index:
    """The register, entry by entry, with everything malformed named."""
    index = Index(present=bool(text))
    if not text:
        return index

    # One walk. A head opens a record and every property line after it fills that
    # record, first spelling winning, so a `·` line standing outside any entry is read
    # by nothing and a repeated one cannot overwrite the entry's own.
    records: list[tuple[re.Match[str], int, dict[str, str]]] = []
    for i, line in enumerate(_unfenced(text)):
        head = _ENTRY_RE.match(line)
        if head is not None:
            records.append((head, i + 1, {}))
            continue
        prop = _PROP_RE.match(line)
        if prop is not None and records:
            records[-1][2].setdefault(prop.group("name"), prop.group("value"))

    seen: dict[str, int] = {}
    for head, line, props in records:
        ident, kind = head.group("id"), head.group("kind")
        where = f"{REGISTER}:{line} {ident}"
        if ident in seen:
            index.malformed.append(f"{where} has more than one entry, the first at "
                                   f"line {seen[ident]}; a finding id is permanent "
                                   "and names one finding")
            continue
        seen[ident] = line
        if kind not in TYPES:
            index.malformed.append(f"{where} is typed {kind!r}, which is none of the "
                                   "four types the register declares")
            continue
        raised = _RAISED_RE.match(props.get("Raised", ""))
        if raised is None:
            index.malformed.append(f"{where} carries no `Raised` line naming the item "
                                   "whose note records it")
            continue
        stated = props.get("Disposition", "")
        state = _STATE_RE.match(stated)
        if state is None or state.group("state") not in DISPOSITIONS:
            index.malformed.append(f"{where} opens its disposition with {stated[:24]!r}, "
                                   "which is none of the three the register declares")
            continue
        index.entries.append(Entry(
            ident=ident, kind=kind,
            raised=raised.group("item").strip(),
            in_prose=raised.group("prose") is not None,
            disposition=state.group("state"),
            restates=props.get("Restates", "").strip(),
            line=line))

    carried = {e.ident for e in index.entries}
    index.malformed += [
        f"{REGISTER}:{e.line} {e.ident} restates {e.restates}, which the register "
        "does not carry"
        for e in index.entries if e.restates and e.restates not in carried]
    return index


def _block_size(lines: list[str], start: int, indent: int) -> int:
    """How many bullets a block header at `start` has under it.

    A bullet deeper than the header is a member, at the first such depth; one at the
    header's depth or shallower ends the block, as does any other content at or above
    it. Blank lines and a member's own continuation lines are neither.
    """
    size = 0
    depth = -1
    for line in lines[start + 1:]:
        if not line.strip():
            continue
        bullet = _BULLET_RE.match(line)
        if bullet is not None:
            here = len(bullet.group("ind"))
            if here <= indent:
                break
            if depth < 0:
                depth = here
            if here == depth:
                size += 1
        elif len(line) - len(line.lstrip()) <= indent:
            break
    return size


def plan(text: str) -> Plan:
    """The checklist's items, and every findings block with the item that raised it."""
    read = Plan(present=bool(text))
    if not text:
        return read

    lines = text.split("\n")
    item = ""
    for i, line in enumerate(lines):
        head = _ITEM_RE.match(line)
        if head is not None:
            item = head.group("label").split(" · ")[0].strip()
            read.items.add(item)
            continue
        block = _BLOCK_RE.match(line)
        if block is not None:
            declared = _COUNTS[block.group("word")]
            read.blocks.append(Block(item=item, line=i + 1, declared=declared,
                                     size=_block_size(lines, i, len(block.group("ind")))))
            continue
        single = _SINGLE_RE.match(line)
        if single is not None:
            read.blocks.append(Block(item=item, line=i + 1, declared=0, size=1))
    return read


def counted(read: Plan) -> dict[str, int]:
    """How many findings each item's note records, over the blocks it declares."""
    per: dict[str, int] = {}
    for block in read.blocks:
        per[block.item] = per.get(block.item, 0) + block.size
    return per


def indexed(index: Index) -> dict[str, int]:
    """How many entries name each item, over the entries the plan counts."""
    per: dict[str, int] = {}
    for entry in index.entries:
        if not entry.in_prose:
            per[entry.raised] = per.get(entry.raised, 0) + 1
    return per


def disagreements(index: Index, read: Plan) -> list[str]:
    """Everything the two sides do not agree on, in the order a reader repairs it."""
    if not index.present:
        return [f"{REGISTER} is not in the checker's corpus, so no finding the plan "
                "records is indexed by anything"]
    if not read.present:
        return [f"{PLAN} is not in the checker's corpus, so the register's entries are "
                "held against nothing"]

    found = list(index.malformed)
    found += [f"{PLAN}:{b.line} declares {b.declared} findings over {b.size} bullet(s)"
              for b in read.blocks if b.declared and b.declared != b.size]
    found += [f"{REGISTER}:{e.line} {e.ident} is raised at {e.raised}, which is not an "
              "item the plan carries"
              for e in index.entries if e.raised not in read.items]

    have, want = indexed(index), counted(read)
    for item in sorted(set(have) | set(want)):
        if item not in read.items:
            continue        # already named above, and once is enough
        mine, theirs = have.get(item, 0), want.get(item, 0)
        if mine != theirs:
            found.append(f"{item}'s note records {theirs} finding(s) and the register "
                         f"indexes {mine}")
    return found
