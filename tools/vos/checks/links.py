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
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

HEADING = "=== links: every cross-reference against what it points at ==="

_LINK_RE = re.compile(r"\]\(([^)\s#]*)(?:#([^)\s]+))?\)")
_SECTION_REF_RE = re.compile(r"§(\d+(?:\.\d+)*)")
_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def sites(name: str, lines: list[int], cap: int = 12) -> str:
    """A file plus the lines to visit, for the checks whose findings are per-line and
    whose repair is always the same visit."""
    shown = (", ".join(str(n) for n in lines[:cap]) + f", and {len(lines) - cap} more"
             if len(lines) > cap else ", ".join(str(n) for n in lines))
    return f"{name}: {len(lines)} line(s): {shown}"


def run(ctx) -> None:
    rep, corpus = ctx.rep, ctx.corpus
    rep.line(HEADING)

    dead: list[str] = []
    unnumbered: dict[str, list[str]] = {}
    exists: dict[str, bool] = {}

    # a link that resolves and a §n.m a heading carries are the overwhelming cases and
    # report nothing, so each is judged before its line is looked up; only a would-be
    # finding pays for the line, and one a fence displays is dropped there as text
    for doc in corpus.docs:
        for m in _LINK_RE.finditer(doc.raw):
            target, frag = m.group(1) or "", m.group(2) or ""
            if _SCHEME_RE.match(target):
                continue                       # off the repository, not ours to hold
            if target.startswith("./"):
                target = target[2:]
            # a relative target resolves against the document that carries it, not the root
            if not target:
                path = doc.name
            else:
                base = PurePosixPath(doc.name).parent
                parts: list[str] = []
                for part in (base / target).parts:
                    if part == "..":
                        if parts:
                            parts.pop()
                    elif part != ".":
                        parts.append(part)
                path = "/".join(parts)

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

    rep.report("K-12", "dead link(s):", dead,
               "every link resolves to a file, and every fragment to a bookmark or heading")

    findings = []
    for number, where in unnumbered.items():
        shown = (", ".join(where[:4]) + f", and {len(where) - 4} more"
                 if len(where) > 4 else ", ".join(where))
        findings.append(f"§{number} is named {len(where)} time(s) and numbered nowhere: {shown}")
    rep.report("K-13", "section reference(s) naming no numbered heading:", findings,
               "every §n.m names a heading some document carries")
    rep.line()
