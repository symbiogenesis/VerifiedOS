# SPDX-License-Identifier: Apache-2.0
"""The findings register, the notes' own findings blocks, and the relation between them.

Three artifacts, one relation. `docs/implementation-checklist.md` carries every item
and, for a landed one, a single line and a link; `docs/completion-log.md` carries the
note each landed item recorded, under a heading spelling the item's label, and a note
records a finding under a count with its bullets beneath it or as a bullet that opens
`Finding`; `docs/findings-register.md` gives that finding an id, a type, the item that
raised it, and a disposition. This module reads all three and states where they
disagree, so that the rule over them and any later tool asking the same question share
one parse rather than two.

**The block's size is its bullets and never its own word.** A note writes `Six
findings.` above six of them, and holding the register against that word would let a
note that lies about itself carry a register that agrees with the lie. So the size is
counted from the bullets and the word is held against the count, which is the
ordinary arithmetic-is-recomputed discipline applied to a document's own enumeration.

**A leading word that is not a count is prose and not a malformed block.** One note
opens a paragraph `Environment findings, booked for later lanes.` and carries three
findings inside it; the note states them in prose rather than under a count, so the
register indexes them by hand and marks them `in prose`. Reading that bullet as a
block this parse could not count would make a permanent finding out of a shape the
register already declares it does not hold. What keeps the reading fail-closed
instead is the comparison itself: a count word this alternation stops recognizing
takes its whole block out of the notes' side, and the entries indexing it are then
entries naming findings the note no longer records, which is a finding either way.

**The log is held total against the plan's landed items in both directions.** A
landed or struck item with no entry is a note that was never written or was lost in
the move, and an entry naming no landed item is a note whose item was struck or
renamed under it; each is named rather than left to be met. Blocks are read in both
documents, because an open item's note still lives in the plan, and a block there is
attributed to the item it sits under exactly as one in the log is attributed to the
heading it sits under.

The register's own template is fenced, and a fence displays text rather than
declaring anything, so the fenced spans are dropped before either pattern runs. That
is the same rule `vos/corpus.py` states for every document the checker reads, applied
here because this parse takes text rather than a `Document`.
"""

import re
from dataclasses import dataclass, field

from vos import figures
from vos.corpus import fence_lines

REGISTER = "docs/findings-register.md"
PLAN = "docs/implementation-checklist.md"
LOG = "docs/completion-log.md"

# The closed vocabularies. A type says what a reader does with the finding and a
# disposition says whether anything is owed; an entry carrying neither in the words
# the register declares is an entry this parse cannot place, which is a finding rather
# than an entry quietly dropped from the comparison.
TYPES = ("owed-act", "upstream-defect", "method", "measurement")
DISPOSITIONS = ("open", "closed", "standing")


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
_ITEM_RE = re.compile(r"^[^\S\r\n]*\* (?:\[(?P<box>[ x])\] |(?P<struck>~~))\*\*(?P<label>[^*\r\n]+?)\*\*")
# A log entry's heading: the item's label as the plan writes it, one heading level
# below the section it sits in and two below the log's own title, a child item of a
# split milestone sitting one level below its parent. A section heading is two hashes
# and is not an entry.
_LOG_ITEM_RE = re.compile(r"^#{3,4} (?P<label>\S[^\r\n]*?)[ \t]*$")
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
    """One findings block of a note: which document and line it is at, whose it is,
    how many bullets it carries, and what its own word claims. `declared` is zero for
    the singleton form, which states no count and carries exactly the one finding its
    bullet is."""

    doc: str
    item: str
    line: int
    size: int
    declared: int


@dataclass
class Plan:
    """The notes' side: every item label the plan carries, the landed and struck ones
    among them, the items the completion log carries an entry for, and every findings
    block either document records."""

    present: bool = False
    log_present: bool = False
    items: set[str] = field(default_factory=set)
    done: set[str] = field(default_factory=set)
    log_items: set[str] = field(default_factory=set)
    blocks: list[Block] = field(default_factory=list)


def _unfenced(text: str) -> list[str]:
    """The document's lines with every fenced span blanked.

    Blanked rather than removed, so that a line number is the document's own and a
    finding sends a reader to the line the register writes.
    """
    lines = text.split("\n")
    return ["" if fenced else line
            for line, fenced in zip(lines, fence_lines(lines), strict=True)]


def _head(label: str) -> str:
    return label.partition(" · ")[0].strip()


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


def _blocks(doc: str, lines: list[str], item_at: dict[int, str]) -> list[Block]:
    """Every findings block of one document, attributed to the item whose span it is in.

    `item_at` gives, for each line that opens an item, that item's label head; a block
    belongs to the last item opened above it, and one above every item belongs to
    nobody, which the comparison then skips as an item the plan does not carry.
    """
    blocks: list[Block] = []
    item = ""
    for i, line in enumerate(lines):
        if i in item_at:
            item = item_at[i]
            continue
        block = _BLOCK_RE.match(line)
        if block is not None:
            declared = _COUNTS[block.group("word")]
            blocks.append(Block(doc=doc, item=item, line=i + 1, declared=declared,
                                size=_block_size(lines, i, len(block.group("ind")))))
            continue
        single = _SINGLE_RE.match(line)
        if single is not None:
            blocks.append(Block(doc=doc, item=item, line=i + 1, declared=0, size=1))
    return blocks


def plan(text: str, log: str = "") -> Plan:
    """The checklist's items, the log's entries, and every findings block either carries.

    The plan is read for every item, the landed and struck ones noted apart; the log is
    read for its entry headings, and both are read for blocks. An absent plan yields a
    `Plan` that is not present, and the comparison then says so once rather than once
    per entry; an absent log is recorded the same way and reported the same way.
    """
    read = Plan(present=bool(text), log_present=bool(log))
    if not text:
        return read

    lines = text.split("\n")
    item_at: dict[int, str] = {}
    for i, line in enumerate(lines):
        head = _ITEM_RE.match(line)
        if head is not None:
            label = _head(head.group("label"))
            item_at[i] = label
            read.items.add(label)
            if head.group("box") == "x" or head.group("struck") is not None:
                read.done.add(label)
    read.blocks.extend(_blocks(PLAN, lines, item_at))

    if log:
        log_lines = _unfenced(log)
        log_at: dict[int, str] = {}
        for i, line in enumerate(log_lines):
            head = _LOG_ITEM_RE.match(line)
            if head is not None:
                label = _head(head.group("label"))
                log_at[i] = label
                read.log_items.add(label)
        read.blocks.extend(_blocks(LOG, log_lines, log_at))
    return read


def counted(read: Plan) -> dict[str, int]:
    """How many findings each item's note records, over the blocks it declares."""
    per: dict[str, int] = {}
    for block in read.blocks:
        per[block.item] = per.get(block.item, 0) + block.size
    return per


def indexed(index: Index) -> dict[str, int]:
    """How many entries name each item, over the entries the notes count."""
    per: dict[str, int] = {}
    for entry in index.entries:
        if not entry.in_prose:
            per[entry.raised] = per.get(entry.raised, 0) + 1
    return per


def disagreements(index: Index, read: Plan) -> list[str]:
    """Everything the sides do not agree on, in the order a reader repairs it."""
    if not index.present:
        return [f"{REGISTER} is not in the checker's corpus, so no finding the plan "
                "records is indexed by anything"]
    if not read.present:
        return [f"{PLAN} is not in the checker's corpus, so the register's entries are "
                "held against nothing"]

    found = list(index.malformed)
    if not read.log_present:
        found.append(f"{LOG} is not in the checker's corpus, so no landed item's note "
                     "is read and the register's entries are held against the plan's "
                     "open notes alone")
    else:
        found += [f"{item} is a landed item {LOG} carries no entry for"
                  for item in sorted(read.done - read.log_items)]
        found += [f"{LOG} carries an entry for {item}, which is not a landed item the "
                  "plan carries"
                  for item in sorted(read.log_items - read.done)]
    found += [f"{b.doc}:{b.line} declares {b.declared} findings over {b.size} bullet(s)"
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
