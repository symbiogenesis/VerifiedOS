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
"""

import re
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


def sites(name: str, lines: list[int], cap: int = 12) -> str:
    """A file plus the lines to visit, for the checks whose findings are per-line and
    whose repair is always the same visit."""
    shown = (", ".join(str(n) for n in lines[:cap]) + f", and {len(lines) - cap} more"
             if len(lines) > cap else ", ".join(str(n) for n in lines))
    return f"{name}: {len(lines)} line(s): {shown}"


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

        for m in _ENTRY_REF_RE.finditer(doc.raw):
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
    rep.line()
