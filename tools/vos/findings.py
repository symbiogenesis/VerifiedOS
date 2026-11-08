# SPDX-License-Identifier: Apache-2.0
"""Parse and cross-check [docs/assurance/findings-register.md](../../docs/assurance/findings-register.md),
[PLAN.md](../../PLAN.md), and [docs/implementation/completion-log.md](../../docs/implementation/completion-log.md).

Validates that:
- Every finding entry in `REGISTER` has a valid `TYPES` kind, `Raised` item, `DISPOSITIONS`
  state, and existing `Restates` target.
- Every landed or struck item in `PLAN` has a single summary bullet linking to its own
  entry in `LOG`, and `LOG` entries correspond 1-to-1 with landed/struck `PLAN` items.
- Every numbered findings block (`"<Word> findings."`) in `PLAN` or `LOG` matches its
  nested bullet count, and the non-prose entries in `REGISTER` for each item match the
  total findings recorded in that item's note.
"""

import re
from dataclasses import dataclass, field

from vos import figures
from vos.corpus import fence_lines, slug
from vos.report import sites

REGISTER = "docs/assurance/findings-register.md"
PLAN = "PLAN.md"
LOG = "docs/implementation/completion-log.md"

TYPES = ("owed-act", "upstream-defect", "method", "measurement")
DISPOSITIONS = ("open", "closed", "standing")

_ENTRY_RE = re.compile(r"^\*\*(?P<id>F-\d{3}[a-z]?)\*\* (?P<kind>[a-z-]+): (?P<what>\S.*)$")
_PROP_RE = re.compile(r"^· (?P<name>Raised|Disposition|Restates): (?P<value>\S.*)$")
_RAISED_RE = re.compile(r"^(?P<item>[^,]+?)(?P<prose>, in prose)?$")
_STATE_RE = re.compile(r"^(?P<state>[a-z-]+)")

# Capitalized English number words (`One`..`Ninety-nine`) from [figures.py](figures.py).
_COUNTS = {figures.words(n).capitalize(): n for n in range(1, 100)}

_ITEM_RE = re.compile(r"^[^\S\r\n]*\* (?:\[(?P<box>[ x])\] |(?P<struck>~~))\*\*(?P<label>[^*\r\n]+?)\*\*")
_LOG_ITEM_RE = re.compile(r"^#{3,6} (?P<label>\S[^\r\n]*?)[ \t]*$")
# Longest words first so hyphenated numbers (`Twenty-three`) match before their prefixes (`Twenty`).
_BLOCK_RE = re.compile(r"^(?P<ind>[^\S\r\n]*)\* \*{0,2}(?P<word>"
                       + "|".join(sorted(_COUNTS, key=len, reverse=True))
                       + r") findings\b")
_SINGLE_RE = re.compile(r"^(?P<ind>[^\S\r\n]*)\* \*{0,2}Finding[,:]")
_BULLET_RE = re.compile(r"^(?P<ind>[^\S\r\n]*)\* ")
_LOG_LINK_RE = re.compile(r"\]\(docs/implementation/completion-log\.md#(?P<anchor>[^()\s]+)\)")


@dataclass(frozen=True)
class Entry:
    """Parsed entry from [docs/assurance/findings-register.md](../../docs/assurance/findings-register.md)."""

    ident: str
    kind: str
    raised: str
    in_prose: bool
    disposition: str
    restates: str
    line: int


@dataclass
class Index:
    """Parsed findings register contents and any structural errors."""

    present: bool = False
    entries: list[Entry] = field(default_factory=list)
    malformed: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Block:
    """Findings bullet block in `PLAN` or `LOG` (`declared == 0` for a singleton `Finding:` bullet)."""

    doc: str
    item: str
    line: int
    size: int
    declared: int


@dataclass
class Plan:
    """Checklist items, completion-log headings/anchors, and findings blocks from `PLAN` and `LOG`."""

    present: bool = False
    log_present: bool = False
    items: set[str] = field(default_factory=set)
    done: set[str] = field(default_factory=set)
    log_items: set[str] = field(default_factory=set)
    log_anchors: dict[str, str] = field(default_factory=dict)
    blocks: list[Block] = field(default_factory=list)


def _unfenced(text: str) -> list[str]:
    """Return lines of `text` with fenced code blocks blanked out to preserve line numbers."""
    lines = text.split("\n")
    return ["" if fenced else line
            for line, fenced in zip(lines, fence_lines(lines), strict=True)]


def _head(label: str) -> str:
    return label.partition(" · ")[0].strip()


def parse(text: str) -> Index:
    """Parse `REGISTER` text into an `Index`, recording malformed entries."""
    index = Index(present=bool(text))
    if not text:
        return index

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
    """Count direct child bullets under the findings block header at `lines[start]`."""
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
    """Extract all `Block`s from `lines` and attribute each to the preceding item in `item_at`."""
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
    """Parse checklist items and findings blocks from `PLAN` (`text`) and `LOG` (`log`)."""
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
                read.log_anchors.setdefault(label, slug(head.group("label")))
        read.blocks.extend(_blocks(LOG, log_lines, log_at))
    return read


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def shapes(text: str, read: Plan) -> list[str]:
    """Report landed or struck items in `PLAN` that violate the single-summary-line + `LOG`-link convention."""
    if not text:
        return [f"{PLAN} is not in the checker's corpus, so no landed item's shape is "
                "read"]
    if not read.done:
        return [f"{PLAN} carries no landed or struck item this rule can read, so the "
                "one-line summary it keeps for each is held against nothing"]

    found: list[str] = []
    lines = _unfenced(text)
    for i, line in enumerate(lines):
        head = _ITEM_RE.match(line)
        if head is None or (head.group("box") != "x" and head.group("struck") is None):
            continue
        label = _head(head.group("label"))
        where = f"{PLAN}:{i + 1} {label}"
        indent = _indent(line)
        summaries: list[int] = []
        extra: list[int] = []
        depth = -1
        in_child = False
        for j in range(i + 1, len(lines)):
            here = lines[j]
            if not here.strip():
                continue
            lead = _indent(here)
            if lead <= indent:
                break
            if _BULLET_RE.match(here) is not None and depth in (-1, lead):
                depth = lead
                in_child = _ITEM_RE.match(here) is not None
                if not in_child:
                    summaries.append(j)
            elif not in_child:
                extra.append(j + 1)

        if not summaries:
            found.append(f"{where} keeps no summary line; a landed item keeps one, "
                         f"linking its entry in {LOG}")
        elif len(summaries) > 1:
            found.append(f"{where} keeps {len(summaries)} summary bullets, at lines "
                         f"{', '.join(str(j + 1) for j in summaries)}; a landed item "
                         f"keeps one, and the rest of its note belongs in {LOG}")
        else:
            anchors = [m.group("anchor") for m in _LOG_LINK_RE.finditer(lines[summaries[0]])]
            own = read.log_anchors.get(label)
            if not anchors:
                found.append(f"{where} keeps a summary line linking no entry in {LOG}")
            elif own is not None and own not in anchors:
                found.append(f"{where} links {', '.join(anchors)} in {LOG} and not its "
                             f"own entry, {own}")
        if extra:
            found.append(f"{sites(where, extra)}, kept beyond its header, one summary "
                         f"line and its child items; that note belongs in {LOG}")
    return found


def counted(read: Plan) -> dict[str, int]:
    """Return `{item_label: total_findings_bullets}` across all `Block`s in `read`."""
    per: dict[str, int] = {}
    for block in read.blocks:
        per[block.item] = per.get(block.item, 0) + block.size
    return per


def indexed(index: Index) -> dict[str, int]:
    """Return `{item_label: entry_count}` across non-prose entries in `index`."""
    per: dict[str, int] = {}
    for entry in index.entries:
        if not entry.in_prose:
            per[entry.raised] = per.get(entry.raised, 0) + 1
    return per


def disagreements(index: Index, read: Plan) -> list[str]:
    """Return all findings-register, completion-log, and block-count disagreements between `index` and `read`."""
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
            continue
        mine, theirs = have.get(item, 0), want.get(item, 0)
        if mine != theirs:
            found.append(f"{item}'s note records {theirs} finding(s) and the register "
                         f"indexes {mine}")
    return found
