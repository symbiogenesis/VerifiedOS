# SPDX-License-Identifier: Apache-2.0
"""Bind proof headers to their cited requirements without duplicating their prose.

The generated manifest names the owner, canonical citation set and normative-body
fingerprint. `--show` reads those bodies from the owner as Markdown when needed.
"""

import argparse
import hashlib
import re
import textwrap
from pathlib import Path

from vos import corpus as corpus_mod
from vos import proofcites
from vos.register import REGISTER, Register, read_register

# The ring compiler owns this file whole; a second writer cannot share it.
EXCLUDED = frozenset({"proofs/RingContract.v"})

# A refusable layout anchor, not a search for arbitrary comment syntax: the shipped
# artifacts open with the licence comment and the ruled explanatory header.
_HEADER = re.compile(r"\A\(\* SPDX-License-Identifier:[^\r\n]*\*\)\r?\n"
                     r"\(\* ={3,}\r?\n")
_HEADER_END = re.compile(r"(?m)^[ \t]*={3,} \*\)\r?$")
WIDTH = 96


class HeaderError(ValueError):
    """An artifact whose header cannot be regenerated without guessing."""


def selected(text: str, reg: Register, region: proofcites.Derived | None = None) -> list[str]:
    """Authored citations in register order, excluding every generated region."""
    if region is None:
        region = proofcites.derived(text)
    if region.faults:
        raise HeaderError("; ".join(region.faults))
    cited = set(proofcites.ids(text, region))
    unknown = cited - reg.id_set
    if unknown:
        raise HeaderError("citations name no live requirement: " + ", ".join(sorted(unknown)))
    if not cited:
        raise HeaderError("the artifact cites no requirement to bind")
    return [ident for ident in reg.ids if ident in cited]


def manifest(text: str, reg: Register) -> str:
    """The compact manifest for this source's canonical authored citations."""
    return _manifest(selected(text, reg), reg)


def _manifest(cited: list[str], reg: Register) -> str:
    """A compact LF manifest; hash exact normative bodies with framed UTF-8 fields.

    The schema prefix and NUL separators distinguish identities and boundaries.
    Parsed entry bodies contain no line endings, so host and guest hash identically.
    Criteria and transitive citations do not enter this normative-body fingerprint.
    """
    payload = "vos-proof-requirements-v1\0" + "".join(
        ident + "\0" + reg.body[ident] + "\0" for ident in cited)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    ids = textwrap.fill(" ".join(cited), width=WIDTH,
                        initial_indent="   Requirements: ", subsequent_indent="      ",
                        break_long_words=False, break_on_hyphens=False)
    return f"   Owner: {REGISTER}\n{ids}\n   SHA256: {digest}"


def show(text: str, reg: Register) -> str:
    """Read the selected normative bodies on demand, as ordinary Markdown."""
    bodies = "\n\n".join(reg.body[ident] for ident in selected(text, reg))
    return f"# Cited requirements\n\nSource: [{REGISTER}]({REGISTER})\n\n{bodies}\n"


def render(text: str, reg: Register) -> str:
    """The artifact with one current manifest, leaving all authored bytes in place."""
    header = _HEADER.match(text)
    end = _HEADER_END.search(text)
    if header is None or end is None:
        raise HeaderError("no ruled opening header follows the licence comment")
    region = proofcites.derived(text)
    if region.faults:
        raise HeaderError("; ".join(region.faults))
    if len(region.spans) > 1:
        raise HeaderError("more than one derived region; the header writer owns one")
    if region.spans and not (
            header.end() <= region.spans[0][0] < region.spans[0][1] <= end.start()):
        raise HeaderError("the derived region is outside the opening header")

    cited = selected(text, reg, region)
    newline = "\r\n" if "\r\n" in text else "\n"
    body = newline + _manifest(cited, reg).replace("\n", newline) + newline + "   "
    if region.spans:
        start, stop = region.spans[0]
        result = text[:start] + body + text[stop:]
    else:
        block = ("   " + proofcites.DERIVED_BEGIN + body + proofcites.DERIVED_END
                 + newline)
        result = text[:end.start()] + block + text[end.start():]
    if set(proofcites.ids(result)) != set(cited):
        raise HeaderError("regeneration changed the authored requirement citation set")
    return result


def plan(root: Path, reg: Register,
         rels: list[str] | None = None) -> tuple[dict[str, str], list[str]]:
    """Changed texts and refusals, with no writes; callers decide when to publish.

    A gate supplies its index-derived paths. The CLI defaults to the working tree,
    including a new proof whose author has not staged it yet.
    """
    selected = proofcites.on_disk(root) if rels is None else rels
    changed: dict[str, str] = {}
    faults: list[str] = []
    for rel in selected:
        if rel in EXCLUDED:
            continue
        try:
            text = (root / rel).read_bytes().decode("utf-8")
            generated = render(text, reg)
        except (OSError, UnicodeDecodeError, HeaderError) as exc:
            faults.append(f"{rel}: {exc}")
            continue
        if generated != text:
            changed[rel] = generated
    return changed, faults


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run.py proofs headers",
        description="Check compact requirement manifests; --show reads their owner prose.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true",
                      help="update generated owner, citation IDs and normative-body SHA256")
    mode.add_argument("--show", metavar="PATH",
                      help="print a proof's cited normative entries as Markdown")
    parser.add_argument("--file", action="append", dest="files", metavar="PATH",
                        help="select a repository-relative proof path; may be repeated")
    args = parser.parse_args(argv)
    if args.show and args.files:
        parser.error("--show selects one proof; omit --file")
    root = corpus_mod.find_root()
    all_sources = set(proofcites.on_disk(root)) - EXCLUDED
    paths = sorted({args.show} if args.show else set(args.files or all_sources))
    invalid = sorted(set(paths) - all_sources)
    if invalid or not paths:
        print("FAIL proof headers: select a non-generated proof in this checkout"
              + (": " + ", ".join(invalid) if invalid else ""))
        return 1
    reg = read_register(corpus_mod.load(root))
    if args.show:
        try:
            print(show((root / args.show).read_bytes().decode("utf-8"), reg), end="")
        except (OSError, UnicodeDecodeError, HeaderError) as exc:
            print(f"FAIL proof headers: {args.show}: {exc}")
            return 1
        return 0
    changed, faults = plan(root, reg, paths)
    if faults:
        print("\n".join(f"FAIL proof headers: {fault}" for fault in faults))
        return 1
    if args.write:
        for rel, text in changed.items():
            (root / rel).write_text(text, encoding="utf-8", newline="")
        print(f"ok proof headers: wrote {len(changed)} of {len(paths)} artifacts; "
              "authored citation sets are unchanged")
        return 0
    if changed:
        print("FAIL proof headers: stale or missing derived regions; "
              "run `python tools/run.py proofs headers --write`")
        print("\n".join(f"  {rel}" for rel in changed))
        return 1
    print(f"ok proof headers: all {len(paths)} manifests match their cited normative bodies")
    return 0
