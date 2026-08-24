# SPDX-License-Identifier: Apache-2.0
"""links: every cross-reference a document makes, against what it points at.

The traces group holds the register's citations of the prose. This holds every other
pointer: the README to the views, the views to each other and back to the register, a
heading cited by its slug, and the §n.m a sentence names without a link at all, which
is the commonest cross-reference here and the only one Markdown cannot render as
broken even in principle. A dead link renders as ordinary text and reads as a working
reference, so nothing but a tool notices. Renaming a heading breaks every slug that
cited it and renumbering a section breaks every §n.m that named it, both silently and
both at a distance from the edit that caused them.

The §n.m half resolves against the numbered headings of the whole repository rather
than one document's, because the numbering is shared: §5.2 is the register's
subsection and the profile's CSR section, and which is meant is the sentence's
business. What the check holds is the weaker property that closes the drift: a number
no document carries at all is a reference to a section that has been renumbered away.

The third form is a sentence naming an entry of *another* document, `the X entry in
[Title](other.md)`, and it is held only in that direction. Within one document the
prose nicknames an entry by its subject rather than by its heading, the FGMT entry and
the tagged-architecture entry naming headings that carry neither word, so a
containment rule over those would report working prose; and a reader who wants one
scrolls to it. Across a document boundary neither holds: the reader cannot see the
target, and the entry can be retitled, merged into another, or split by an edit made
wholly inside the other file, which leaves a pointer that resolves as a link and names
nothing. That is the case this rule takes, so a name written as an *entry* is required
to be carried by a heading over there while a name written as a *rationale* or an
*argument* claims no heading and is not read here at all.

The fourth form is a pointer written as a *path* rather than as a link, and the one
place in the repository where that pointer carries a licence obligation:
[THIRD-PARTY.md](../../../THIRD-PARTY.md)'s vendored and fetched tables discharge
their notice obligations by naming the file each component's terms arrive in, and a
cell naming `model/dependencies/elfio/LICENSE.txt` is text where a cell naming
[model/LICENCE](model/LICENCE) is a link. The link half is K-12's. The other half
reached no rule at all, so deleting a licence file left a page claiming to
redistribute a component whose terms are nowhere in the tree, with every rule green.
"""

import re
from collections.abc import Iterator
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from vos.corpus import HEADING_RE, Document, slug

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== links: every cross-reference against what it points at ==="

_LINK_RE = re.compile(r"\]\(([^)\s#]*)(?:#([^)\s]+))?\)")
_SECTION_REF_RE = re.compile(r"§(\d+(?:\.\d+)*)")
_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)

# `the <name> entry in [Title](other.md)`. The name is at most five tokens and may not
# contain `the`, which is what keeps the capture off the sentence in front of it: the
# prose routinely writes `the hop the memory-encryption entry`, and a run of tokens
# reaching back past that second `the` names a phrase rather than an entry.
_ENTRY_REF_RE = re.compile(
    r"(?<![\w-])the ((?!the[ -])[A-Za-z0-9][\w./'-]*"
    r"(?:[ -](?:and[ -])?(?!the[ -])[A-Za-z0-9][\w./'-]*){0,4}?) (?:entry|entries)"
    r"\s+(?:in|of)\s+\[[^\]]*\]\(([^)\s#]+)\)"
)

def _entry_refs(raw: str) -> Iterator[re.Match[str]]:
    """Every `_ENTRY_REF_RE` match, found from the rare word rather than the common one.

    A plain scan of that pattern anchors on `the `, which the corpus carries many
    thousands of times, and each one pays an attempt at the five-token name: measured
    over this corpus, 137 ms to find five matches, most of what the whole group cost.
    The entry word is the part a match cannot do without and the corpus carries under
    a thousand of, so the walk goes the other way: every occurrence of `entr`, the
    line it sits on, and one anchored attempt at each `the ` on that line before it,
    which finds the same five in about ten. The head of a match cannot
    span lines, because no separator inside it admits a newline, so the line bound
    loses nothing; the tail past the entry word may, so each attempt runs against the
    whole text. Matches come back leftmost-first and non-overlapping, which is the
    contract `finditer` kept.
    """
    found: dict[int, re.Match[str]] = {}
    tried: set[int] = set()
    k = raw.find("entr")
    while k != -1:
        line_start = raw.rfind("\n", 0, k) + 1
        t = raw.find("the ", line_start, k)
        while t != -1:
            if t not in tried:
                tried.add(t)
                if m := _ENTRY_REF_RE.match(raw, t):
                    found[t] = m
            t = raw.find("the ", t + 1, k)
        k = raw.find("entr", k + 1)
    last_end = -1
    for start in sorted(found):
        if start >= last_end:
            last_end = found[start].end()
            yield found[start]


# The two tables of THIRD-PARTY.md whose last column names where a component's terms
# arrive. The other tables on that page are deliberately out of reach: the submodule
# table names terms without naming a file this tree carries, and the read-ahead tables
# name a file inside an upstream nothing here tracks, which is what "read ahead"
# means.
THIRD_PARTY = "THIRD-PARTY.md"
LICENCE_TABLES = ("Vendored, and redistributed here", "Fetched at build time")
LICENCE_COLUMN = "License text"

_CELL_PATH_RE = re.compile(r"`([^`]+)`")
_CELL_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s#]+)\)")
_H2_RE = re.compile(r"## +(.*)")


def _licence_texts(ctx: Context) -> tuple[list[tuple[int, str, bool]], list[str]]:
    """Every path THIRD-PARTY.md names as a component's licence text, with its line.

    Fail-closed in the reading, which matters more here than in most of this group:
    the claim is about redistribution, so a table this rule cannot find has to be a
    finding rather than a comparison made against an empty set. The page missing, a
    named section missing, a section carrying no table, and a table whose last column
    is no longer the licence text are four separate stops, each worded as itself.

    The third member of each tuple says whether the cell wrote a link, because a link
    at a file that is not there at all is K-12's finding and pricing one defect as two
    is what this group already refuses at K-59.
    """
    doc = ctx.corpus.get(THIRD_PARTY)
    if doc is None:
        return [], [f"{THIRD_PARTY} is not in the repository, so no component's "
                    "licence text can be located at all"]

    found: list[tuple[int, str, bool]] = []
    faults: list[str] = []
    for wanted in LICENCE_TABLES:
        rows = [(i, line) for i, line in _table_rows(doc, wanted)]
        if not rows:
            faults.append(f"{THIRD_PARTY} carries no table under '{wanted}', so the "
                          "components it lists cannot be read")
            continue
        header = [c.strip() for c in rows[0][1].strip().strip("|").split("|")]
        if not header or header[-1] != LICENCE_COLUMN:
            faults.append(f"{THIRD_PARTY}:{rows[0][0] + 1} the '{wanted}' table's last "
                          f"column is '{header[-1] if header else ''}' and not "
                          f"'{LICENCE_COLUMN}', so this rule is reading the wrong cell")
            continue
        for i, line in rows[2:]:
            cell = line.strip().strip("|").split("|")[-1].strip()
            link = _CELL_LINK_RE.search(cell)
            if link:
                found.append((i + 1, resolve(THIRD_PARTY, link.group(1)), True))
                continue
            paths = _CELL_PATH_RE.findall(cell)
            if not paths:
                faults.append(f"{THIRD_PARTY}:{i + 1} names no licence text at all, so "
                              "the row claims a component and locates its terms nowhere")
                continue
            found += [(i + 1, resolve(THIRD_PARTY, p), False) for p in paths]
    return found, faults


def _table_rows(doc: Document, heading: str) -> Iterator[tuple[int, str]]:
    """The `|`-led lines of the first table under a `##` heading, header row first."""
    inside = False
    started = False
    for i, line in enumerate(doc.lines):
        if doc.fenced[i]:
            continue
        if m := _H2_RE.match(line):
            if started:
                return
            inside = m.group(1).strip() == heading
            continue
        if not inside:
            continue
        if line.startswith("|"):
            started = True
            yield i, line
        elif started:
            return


def resolve(base: str, target: str) -> str:
    """A relative link target, against the document that carries it and not the root."""
    if not target:
        return base
    parts: list[str] = []
    for part in (PurePosixPath(base).parent / target).parts:
        if part == "..":
            if parts:
                parts.pop()
        elif part != ".":
            parts.append(part)
    return "/".join(parts)


def headings(doc: Document, cache: dict[str, list[str]]) -> list[str]:
    """Every heading of a document, as slugs, read once per document per run.

    The corpus keeps a document's headings only as members of `targets`, which holds
    its declared bookmarks too. This rule claims a *heading*, so it reads the headings
    rather than the union: an id that happened to contain the name would otherwise
    satisfy a claim about a title.
    """
    if doc.name not in cache:
        cache[doc.name] = [slug(m.group(1)) for _, m in doc.unfenced("#", HEADING_RE)]
    return cache[doc.name]


def run(ctx: Context) -> None:
    rep, corpus = ctx.rep, ctx.corpus
    rep.line(HEADING)

    dead: list[str] = []
    unnumbered: dict[str, list[str]] = {}
    exists: dict[str, bool] = {}
    stale: list[str] = []
    heads: dict[str, list[str]] = {}
    attributed = 0

    # a link that resolves and a §n.m a heading carries are the overwhelming cases and
    # report nothing, so each is judged before its line is looked up; only a would-be
    # finding pays for the line, and one a fence displays is dropped there as text
    for doc in corpus.docs:
        for m in _LINK_RE.finditer(doc.raw):
            target, frag = m.group(1) or "", m.group(2) or ""
            if _SCHEME_RE.match(target):
                continue                       # off the repository, not ours to hold
            path = resolve(doc.name, target.removeprefix("./"))

            if path not in exists:
                absolute = ctx.root / path
                exists[path] = absolute.exists() or path in corpus.gitlinks

            if not exists[path]:
                bad = f"points at {path}, which is not in the repository"
            elif frag and path in corpus and frag not in corpus.by_name[path].targets:
                bad = f"points at {path}#{frag}, which is no bookmark or heading there"
            else:
                continue
            if doc.is_fenced(m.start()):
                continue
            dead.append(f"{doc.name}:{doc.at(m.start())} {bad}")

        for m in _SECTION_REF_RE.finditer(doc.raw):
            number = m.group(1)
            if number in corpus.numbered or doc.is_fenced(m.start()):
                continue
            unnumbered.setdefault(number, []).append(f"{doc.name}:{doc.at(m.start())}")

        for m in _entry_refs(doc.raw):
            name, target = m.group(1), m.group(2)
            if _SCHEME_RE.match(target) or doc.is_fenced(m.start()):
                continue
            other = corpus.get(resolve(doc.name, target.removeprefix("./")))
            # a target this repository does not carry is K-12's finding, and reporting
            # it twice would price one defect as two
            if other is None:
                continue
            attributed += 1
            wanted = slug(name)
            if not any(wanted in head for head in headings(other, heads)):
                stale.append(f"{doc.name}:{doc.at(m.start())} names the {name} entry of "
                             f"{other.name}, which carries no such heading")

    rep.report("K-12", "dead link(s):", dead,
               "every link resolves to a file, and every fragment to a bookmark or heading")

    findings = []
    for number, where in unnumbered.items():
        shown = (", ".join(where[:4]) + f", and {len(where) - 4} more"
                 if len(where) > 4 else ", ".join(where))
        findings.append(f"§{number} is named {len(where)} time(s) and numbered nowhere: {shown}")
    rep.report("K-13", "section reference(s) naming no numbered heading:", findings,
               "every §n.m names a heading some document carries")

    ctx.shared["entry_refs"] = attributed
    rep.report("K-59", "entry reference(s) their target document no longer carries:", stale,
               f"all {attributed} entries a document names in another are headings there")

    # The membership is the index and not the filesystem, which is the whole of what
    # separates this from K-12: a licence file present but untracked is one this
    # repository does not redistribute, so the page's claim over it is false while the
    # file sits right there. `tracked` is the index's own listing, so a licence text
    # staged for deletion reports here before the deletion lands.
    texts, faults = _licence_texts(ctx)
    tracked = set(corpus.tracked)
    findings = list(faults)
    for line, path, was_link in texts:
        if path in tracked:
            continue
        if was_link and not (ctx.root / path).exists():
            continue                           # K-12's finding; not priced twice
        findings.append(
            f"{THIRD_PARTY}:{line} locates a component's licence text at {path}, which "
            "the index does not carry, so the page claims to redistribute terms this "
            "repository does not ship")
    ctx.shared["licence_texts"] = len(texts)
    rep.report("K-80", "licence text(s) the repository does not carry:", findings,
               f"all {len(texts)} licence texts the third-party page locates are "
               "tracked files")
    rep.line()
