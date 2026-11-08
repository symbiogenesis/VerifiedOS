#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Answer, before work starts, what an edit re-opens in the apex statement.

    tools/run.py blast --field composed_schedulability
    tools/run.py blast --artifact proofs/SomeWorkstream.v
    tools/run.py blast R-07-015           # one register entry, both its ends
    tools/run.py blast                    # every field with its consumers

Reads `Vocabulary` fields and consumer seams from
[proofs/ApexTheorem.v](../../../proofs/ApexTheorem.v) via [vos/apex.py](../apex.py), field
bindings (`Authored by` and `Instantiated by`) from
[docs/assurance/field-bindings.md](../../../docs/assurance/field-bindings.md) via
[vos/fieldbindings.py](../fieldbindings.py), and proof requirement citations via
[vos/proofcites.py](../proofcites.py). Fails closed if any statement in
`ApexTheorem.v` cannot be parsed completely.
"""

import argparse
import re
from collections import deque
from pathlib import Path

from vos import apex, fieldbindings, proofcites
from vos.corpus import find_root
from vos.register import REQ_TOKEN_RE

# Split cell text on whitespace and Markdown link/code-span delimiters.
_TOKEN_SPLIT_RE = re.compile(r"[\s\[\]()`,]+")


def _seam_conclusions(record: apex.ApexRecord) -> dict[str, str]:
    """Return `{seam_name: concluded_field}` for every `seam_*` definition in `record`."""
    return {name: fields[-1] for name, fields in record.def_fields.items()
            if name.startswith("seam_")}


def _matches(cell: str, artifact: str) -> bool:
    """Return whether an `Instantiated by` cell token-matches `artifact` (excluding `none yet`)."""
    cell = cell.strip()
    if cell == "none yet":
        return False
    return artifact in _TOKEN_SPLIT_RE.split(cell)


def field_lines(record: apex.ApexRecord, conclusions: dict[str, str],
                field: str) -> list[str]:
    out = [f"field {field}", "  consumed by:"]
    for consumer in record.consumers[field]:
        if consumer in conclusions:
            role = " (its conclusion)" if conclusions[consumer] == field else " (a premise)"
        else:
            role = ""
        out.append(f"    {consumer}{role}")

    # the conditional trail: premise-consuming seams conclude fields with their own
    # consumers, and so on until nothing new is reached
    trail: list[str] = []
    seen = {field}
    queue = deque([field])
    while queue:
        current = queue.popleft()
        for consumer in record.consumers[current]:
            if consumer not in conclusions or conclusions[consumer] == current:
                continue
            concluded = conclusions[consumer]
            if concluded not in seen:
                seen.add(concluded)
                trail.append(f"    {consumer} concludes {concluded}")
                queue.append(concluded)
    if trail:
        out.append("  downstream, only if a re-proved seam's conclusion statement must change:")
        out.extend(trail)
    out.append("  and last, always: composition_meta_lemma, the R-18-031(b) linking theorem")
    return out


def _authoring(rows: list[fieldbindings.Row], ident: str) -> list[str]:
    """The Prop fields one register entry is named as the author of.

    An id is matched as an id and never as a token: the Authored-by cells write one
    inside parentheses and one in the possessive, so a token split answers neither,
    where reading the ids a cell names answers both and cannot pair `R-05-159` with
    `R-05-159a`.
    """
    return [row.field for row in rows if ident in REQ_TOKEN_RE.findall(row.authored_by)]


def _cited_by(root: Path) -> tuple[list[tuple[str, str]], list[str]]:
    """Every proof artifact in the working tree, and why any of them would not read."""
    return proofcites.read(root, proofcites.on_disk(root))


def _requirement_lines(record: apex.ApexRecord, conclusions: dict[str, str],
                       fields: list[str], ident: str,
                       pairs: list[tuple[str, str]]) -> tuple[int, list[str]]:
    """One requirement's two ends: the fields it authors, and the proofs citing it.

    The constant count is taken only for the artifacts that cite the entry, because it
    wants the comment-stripping walk and that walk is priced per megabyte: over the
    whole tree it is most of a second, and over the handful an entry reaches it is not
    worth a flag.
    """
    out: list[str] = []
    if fields:
        out.append(f"requirement {ident} authors: {', '.join(fields)}")
    else:
        out.append(f"requirement {ident} authors no Prop field of the Vocabulary record")
    out.append("")
    for f in fields:
        out.extend(field_lines(record, conclusions, f))
        out.append("")

    citing = [(rel, count, text) for rel, text in pairs
              if (count := sum(1 for i in proofcites.ids(text) if i == ident))]
    if citing:
        out.append(f"proof artifacts citing {ident}, which is an argument from the "
                   f"entry and not a discharge of it:")
        out.extend(f"  {rel}: {count} citation(s), among "
                   f"{len(proofcites.names(text))} constant(s) defined"
                   for rel, count, text in citing)
    else:
        out.append(f"no proof artifact under {proofcites.PROOFS}/ cites {ident}")
    return len(fields) + len(citing), out


def report(root: Path, field: str | None, artifact: str | None,
           requirement: str | None = None) -> tuple[int, list[str]]:
    """One whole run as data, the exit code and the lines to print, so the caller
    decides what to do with the verdict rather than parsing what was printed."""
    out: list[str] = []

    apex_path = root / apex.APEX
    if not apex_path.is_file():
        out.append(f"FAIL: {apex.APEX} is not in the repository")
        return 1, out
    record = apex.read(apex_path)
    # A statement the parse could not read whole would answer this question over a field
    # list short by exactly the fields nobody can name and a blast radius short by
    # exactly the consumers nobody saw, which is the one way this tool can be
    # confidently wrong: what it prints is what an editor takes to be the whole of what
    # an edit re-opens, and a short answer here reads as a small radius. Refused rather
    # than narrowed.
    if record.unread:
        out.extend(f"FAIL: {said}" for said in record.unread)
        return 1, out
    conclusions = _seam_conclusions(record)

    if bool(requirement):
        if not REQ_TOKEN_RE.fullmatch(requirement):
            out.append(f"'{requirement}' is no requirement id; the form is R-nn-nnn "
                       "with an optional letter suffix")
            return 1, out
        bindings_path = root / fieldbindings.BINDINGS
        if not bindings_path.is_file():
            out.append(f"FAIL: {fieldbindings.BINDINGS} is not in the repository")
            return 1, out
        rows = fieldbindings.rows(bindings_path.read_text(encoding="utf-8"))
        fields = _authoring(rows, requirement)
        drifted = [f for f in fields if f not in record.field_set]
        if drifted:
            out.append(f"FAIL: {fieldbindings.BINDINGS} row(s) naming no Prop field "
                       f"of the record: {', '.join(drifted)}")
            return 1, out
        pairs, faults = _cited_by(root)
        found, lines = _requirement_lines(
            record, conclusions, fields, requirement, pairs)
        out.extend(lines)
        out.extend(f"FAIL: {fault}" for fault in faults)
        return (0 if found and not faults else 1), out

    if bool(field):
        if field not in record.field_set:
            out.append(f"no Prop field '{field}' in the Vocabulary record; the fields are:")
            out.extend(f"  {f}" for f in record.fields)
            return 1, out
        out.extend(field_lines(record, conclusions, field))
        return 0, out

    if bool(artifact):
        bindings_path = root / fieldbindings.BINDINGS
        if not bindings_path.is_file():
            out.append(f"FAIL: {fieldbindings.BINDINGS} is not in the repository")
            return 1, out
        rows = fieldbindings.rows(bindings_path.read_text(encoding="utf-8"))
        hits = [row.field for row in rows if _matches(row.instantiated_by, artifact)]
        if not hits:
            out.append(f"{fieldbindings.BINDINGS} binds no field to an artifact "
                       f"matching '{artifact}'")
            return 1, out
        drifted = [f for f in hits if f not in record.field_set]
        if drifted:
            out.append(f"FAIL: {fieldbindings.BINDINGS} row(s) naming no Prop field "
                       f"of the record: {', '.join(drifted)}")
            return 1, out
        out.append(f"artifact {artifact} instantiates: {', '.join(hits)}")
        out.append("")
        for f in hits:
            out.extend(field_lines(record, conclusions, f))
            out.append("")
        return 0, out

    out.append("the Vocabulary record's Prop fields and their consumers:")
    out.extend(f"  {f}  <=  {', '.join(record.consumers[f])}" for f in record.fields)
    out.append("query one with --field <name>, or an instantiating artifact with "
               "--artifact <path>")
    return 0, out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        suggest_on_error=True, description="What an edit re-opens in the apex statement.")
    # A bare positional, because `blast R-07-015` is how the question is asked out
    # loud; it is checked against the other two here rather than in a mutually
    # exclusive group, which would have to be told a positional's default is not a
    # value the caller gave.
    parser.add_argument("requirement", nargs="?",
                        help="a requirement id, whose authored fields and citing proof "
                             "artifacts are both reported")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--field", help="one Prop field of the Vocabulary record")
    group.add_argument("--artifact",
                       help="a proof development, named by a whole token of its "
                            "Instantiated-by cell")
    args = parser.parse_args(argv)
    if args.requirement and (args.field or args.artifact):
        parser.error("a requirement id is a query of its own; it takes neither "
                     "--field nor --artifact beside it")

    code, out = report(find_root(), args.field, args.artifact, args.requirement)
    print("\n".join(out))
    return code

