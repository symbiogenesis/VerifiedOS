# SPDX-License-Identifier: Apache-2.0
"""Render the reviewed format inventory and refuse unsupported evidence claims.

Schema 1 deliberately records absent Narcissus descriptors only. Reference codecs
are separate evidence and cannot be promoted to descriptors by editing a status.
The first real descriptor must introduce the bidirectional binding rule proposed
in the inventory. This check is source accounting, not proof-kernel evidence.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from vos import proofs
from vos.jsonutil import unique_object
from vos.schema import validate

SOURCE = "interfaces/wire-formats.json"
SCHEMA = "interfaces/wire-formats.schema.json"
ARTIFACT = "docs/assurance/wire-format-inventory.md"
CROWN = "docs/assurance/crown-jewels.md"
REGISTER = "docs/requirements-register.md"
REQUIRED_CLASSES = frozenset({
    "rrc", "mlme", "nas", "usb", "image", "media", "font", "archive",
    "document", "pack", "manifest", "x509", "module-manifest",
    "module-certificate", "module-endorsement", "module-message", "ensemble",
})
_NARCISSUS = re.compile(r"\b(?:Narcissus|CorrectDecoder|CorrectEncoder)\b")


class InventoryError(ValueError):
    """An inventory is incomplete, stale, or claims evidence it cannot bind."""


@dataclass(frozen=True)
class Entry:
    key: str
    name: str
    classes: tuple[str, ...]
    requirements: tuple[str, ...]
    owner: str
    transcription: str
    canonicity: str
    evidence: str
    references: tuple[str, ...]
    members: tuple[str, ...]


def _text(raw: object, where: str) -> str:
    if not isinstance(raw, str) or not raw.strip() or any(c in raw for c in "\r\n|"):
        raise InventoryError(f"{where}: expected nonempty single-line text without pipes")
    return raw


def _file(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative:
        raise InventoryError(f"unsafe repository path: {relative}")
    found = root / path
    if not found.is_file() or not found.resolve().is_relative_to(root.resolve()):
        raise InventoryError(f"missing or external inventory input: {relative}")
    return found


def _read(root: Path, relative: str) -> str:
    try:
        return _file(root, relative).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise InventoryError(f"cannot read {relative}: {exc}") from exc


def _table_members(root: Path, table: dict[str, str] | None) -> tuple[str, ...]:
    if table is None:
        return ()
    path, heading, until = table["path"], table["heading"], table["until"]
    source = _read(root, path)
    if source.count(heading) != 1:
        raise InventoryError(f"{path}: member-table heading changed")
    tail = source.split(heading, 1)[1]
    if until not in tail:
        raise InventoryError(f"{path}: member-table end changed")
    section = tail.split(until, 1)[0]
    rows = [line.strip() for line in section.splitlines() if line.lstrip().startswith("|")]
    if len(rows) < 3 or rows[0].split("|")[1].strip() not in {"Operation", "Id"}:
        raise InventoryError(f"{path}: missing or unsupported member-table header")
    if not all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in rows[1].split("|")[1:-1]):
        raise InventoryError(f"{path}: unsupported member-table separator")
    collected: list[str] = []
    for row in rows[2:]:
        match = re.match(r"\|\s+`([^`]+)`\s+\|", row)
        if match is None:
            raise InventoryError(f"{path}: unsupported grammar member row: {row}")
        collected.append(_text(match.group(1), "grammar member"))
    members = tuple(collected)
    if not members or len(set(members)) != len(members):
        raise InventoryError(f"{path}: empty or duplicated member table")
    return members


def load(root: Path) -> tuple[Entry, ...]:
    """Validate the source, live member tables and the current descriptor absence."""
    try:
        raw: object = json.loads(_read(root, SOURCE), object_pairs_hook=unique_object)
        validate(root / SCHEMA, raw)
    except ValueError as exc:
        raise InventoryError(f"{SOURCE}: {exc}") from exc
    data = cast(dict[str, Any], raw)
    row10 = [line for line in _read(root, CROWN).splitlines() if line.startswith("| 10 |")]
    if len(row10) != 1:
        raise InventoryError("crown-jewel row 10 is missing or duplicated")
    # The specification cell is held; integrating a truthful status may change its
    # last cell without silently adding a new member class to this reviewed set.
    specification = row10[0].split("|")[2].strip()
    digest = hashlib.sha256(specification.encode("utf-8")).hexdigest()
    if data["reviewed_row10_sha256"] != digest:
        raise InventoryError("row 10 membership changed: review coverage before regenerating")
    classes = data["classes"]
    if set(classes) != REQUIRED_CLASSES:
        raise InventoryError("row 10 member-class coverage set changed or is incomplete")
    for key, phrase in classes.items():
        if phrase not in specification:
            raise InventoryError(f"class {key}: source phrase absent from row 10")
    register = _read(root, REGISTER)
    owner_text = _read(root, "docs/assurance/unassigned-proof-map.md") + _read(
        root, "PLAN.md")
    # Each proof source is read, and its comments blanked, at most once per call: the
    # references name a few sources several times, and the absence scan below reads
    # every source again.
    texts: dict[str, str] = {}
    codes: dict[str, str] = {}

    def text_of(relative: str) -> str:
        if relative not in texts:
            texts[relative] = _read(root, relative)
        return texts[relative]

    def code_of(relative: str) -> str:
        if relative not in codes:
            codes[relative] = proofs.strip_comments(text_of(relative))
        return codes[relative]

    entries: list[Entry] = []
    seen: set[str] = set()
    covered: set[str] = set()
    for entry in data["entries"]:
        key = entry["id"]
        if key in seen:
            raise InventoryError(f"duplicate entry id: {key}")
        seen.add(key)
        memberships = tuple(entry["classes"])
        if set(memberships) - REQUIRED_CLASSES:
            raise InventoryError(f"{key}: unknown member class")
        covered.update(memberships)
        requirements = tuple(entry["requirements"])
        for requirement in requirements:
            if f"**{requirement}**" not in register:
                raise InventoryError(f"{key}: unknown requirement {requirement}")
        owner = entry["owner"]
        if owner != "none" and (not re.fullmatch(r"(?:U-\d+[a-z]*|[A-Z]\d+(?:\.\d+)*[a-z]*)", owner)
                                or f"**{owner} ·" not in owner_text):
            raise InventoryError(f"{key}: owner {owner} is not a landed work item")
        references = tuple(entry["references"])
        for reference in references:
            path, separator, symbol = reference.partition("#")
            text_of(path)
            if separator and (not path.endswith(".v") or not re.search(
                        r"\b(?:Definition|Fixpoint|Record|Inductive|Theorem|Lemma)\s+"
                        + re.escape(symbol) + r"\b", code_of(path))):
                raise InventoryError(f"{key}: missing proof symbol {reference}")
        transcription = entry["transcription"]
        if (transcription == "NAS grammar required") != ("nas" in memberships):
            raise InventoryError(f"{key}: NAS exception must be explicitly and exclusively flagged")
        entries.append(Entry(key, entry["name"], memberships, requirements,
                             owner, transcription, entry["canonicity"],
                             entry["evidence"], references,
                             _table_members(root, entry["members_from"])))
    if REQUIRED_CLASSES - covered:
        raise InventoryError(f"unrepresented row 10 classes: {sorted(REQUIRED_CLASSES - covered)}")
    if "idl-mapping" not in seen:
        raise InventoryError("row 3's IDL wire-format mapping is unrepresented")
    sources = sorted((root / "proofs").rglob("*.v"))
    if not sources:
        raise InventoryError("no proof sources: descriptor absence cannot be inspected")
    for source in sources:
        relative = source.relative_to(root).as_posix()
        # A new library use is a finding, including support modules. It cannot hide
        # behind the old empty inventory. Alias/load-path conventions need review
        # when U-13 selects an import path; no general Rocq semantic scan is claimed.
        # A blanked comment leaves at least a space behind, so it joins no two words:
        # a name the blanked source carries, the raw source carries too, and a source
        # naming none needs no blanking.
        if _NARCISSUS.search(text_of(relative)) and _NARCISSUS.search(code_of(relative)):
            raise InventoryError(f"{source.relative_to(root)}: Narcissus use requires "
                                 "descriptor bindings and the proposed bidirectional rule")
    return tuple(entries)


def _link(reference: str) -> str:
    path, separator, symbol = reference.partition("#")
    label = f"{Path(path).name}{':' + symbol if separator else ''}"
    # A Rocq constant is text, not a Markdown anchor. Link the real file.
    return f"[{label}](../../{path})"


def emit(root: Path) -> str:
    """Generate the complete view from the authored inventory and source tables."""
    entries = load(root)
    source_hash = hashlib.sha256((root / SOURCE).read_bytes()).hexdigest()
    lines = [
        "# Wire-format inventory", "",
        f"<!-- Generated from {SOURCE} by vos.wire_formats.emit; do not edit. -->",
        f"<!-- Source SHA256: {source_hash} -->", "",
        "This is U-12's inventory of the attacker-facing format families the current "
        "design names, including crown-jewel row 10's member classes and row 3's IDL "
        "mapping. The authored source is [wire-formats.json](../../interfaces/wire-formats.json). "
        "A composition must specialize each open family into exact versions, subsets, "
        "byte/field/depth limits and descriptor identities before admitting it. "
        "The release's still-image, audio, container, font and document selections "
        "remain open; a family row does not choose a format or admit an implementation.", "",
        "Every Narcissus descriptor is absent in this inventory. Existing hand-written "
        "Gallina codecs, abstract format conditions and generated ring encodings are "
        "identified separately. Their theorems do not establish a Narcissus derivation, "
        "copy-once implementation, verified lowering or descriptor-to-standard fidelity. "
        "No R-05-042 admission or crown-jewel completion follows from this document.", "",
        "## Reading an entry", "",
        "`none authored` means no hand-transcribed descriptor is present; it does not "
        "certify a future generator. `NAS grammar required` records R-05-050's explicit "
        "exception and its owed differential corpus. `reference codec only` marks "
        "hand-authored executable evidence that cannot be shipped as a substitute "
        "for the required derived parser. The owner is a work item or literal `none`; "
        "`none` is an unpriced descriptor obligation, not a waiver. U-14 selects either "
        "the pack manifest or immutable-module manifest as its first measured descriptor.", "",
        "Canonicity means decode injectivity on the entire admissible byte language "
        "and re-encoding an accepted input unchanged, in addition to the correctness "
        "pair. Each identity-consuming site must name its descriptor and theorem "
        "under R-05-051a through R-05-051c. A role-gated entry must prove canonicity "
        "before signature, name, content-address, cache-key or equality use; recording "
        "the gate does not authorize that use. Differential tests do not discharge it.", "",
        "## Member-class coverage", "",
        "| Crown-jewel row 10 class | Inventory entries |",
        "| --- | --- |",
    ]
    for cls in sorted(REQUIRED_CLASSES):
        matching = ", ".join(f"[{entry.name}](#{entry.key})" for entry in entries
                             if cls in entry.classes)
        lines.append(f"| `{cls}` | {matching} |")
    lines += ["", "## Format entries", ""]
    for entry in entries:
        lines += [f"### {entry.name} <a id=\"{entry.key}\"></a>", "",
                  f"- Descriptor: **absent**. Owner: **{entry.owner}**.",
                  f"- Hand transcription: **{entry.transcription}**.",
                  f"- Canonicity: {entry.canonicity}",
                  f"- Current evidence: {entry.evidence}",
                  "- Requirements: " + ", ".join(entry.requirements) + "."]
        if entry.references:
            lines.append("- Sources: " + ", ".join(_link(ref) for ref in entry.references) + ".")
        if entry.members:
            lines.append("- Forms generated from the owning grammar: "
                         + ", ".join(f"`{member}`" for member in entry.members) + ".")
        lines.append("")
    lines += [
        "## Validation and the proposed descriptor rule", "",
        "K-88 can regenerate this view with `vos.wire_formats.emit`. The source reader "
        "refuses a missing member class or owner, unknown requirement, duplicate ID, "
        "missing reference symbol, changed reviewed row-10 membership, absent or "
        "duplicated grammar table, and any attempt to promote an absent descriptor. "
        "Module operations and ensemble forms are read from their contracts, so "
        "adding a form changes this view. Schema 1 scans every `proofs/**/*.v` source "
        "after stripping comments and refuses Narcissus, CorrectDecoder or CorrectEncoder "
        "use until explicit descriptor bindings are introduced. This conservative "
        "source check neither parses Rocq dependency aliases nor verifies a theorem.", "",
        "**Proposed rule, K-id owed:** when U-13 fixes the library/import identity and "
        "U-14 authors the first descriptor, register one manifest record per actual "
        "descriptor: inventory ID, proof path, fully qualified format constant, "
        "CorrectDecoder and CorrectEncoder proposition constants, canonicity constant "
        "or an explicit prohibition on identity roles, derivation inputs, hand-transcription "
        "flag, owner and review record. The rule must compare the inventory-to-manifest "
        "and manifest-to-compiled-symbol directions over the complete proof gate source "
        "and dependency closure. Missing, duplicate, unknown, orphaned or extra "
        "descriptors fail; each constant must resolve to the named descriptor's "
        "audited proposition in a fresh proof receipt. An empty set succeeds only "
        "with the explicit absent status and no descriptor-producing module. A "
        "declaration annotation alone never establishes Narcissus derivation or "
        "semantic correspondence. Mutants must drop each direction, substitute a "
        "reference codec, remove canonicity from an identity use, and add an "
        "unlisted descriptor. Add the checker registry row and mutation case with "
        "the allocated ID; U-12 proposes this contract and does not install that "
        "future proof-aware rule.", "",
        "## Remaining foundation dependencies", "",
        "U-13 owes Narcissus's pinned Rocq compatibility, assumptions and licence "
        "disposition. U-14 owes the first real descriptor, correctness pair, "
        "whole-language canonicity and measured cost. Every subsequent descriptor "
        "needs its own priced owner, bounded profile and independent R-05-150 review. "
        "RRC also needs R-18-029's verified ASN.1 front end; NAS needs its four-reference "
        "differential corpus. Q2b owns target lowering evidence. Q23b's frame contract "
        "and Q24a's module grammar supply statements, while Q23c/Q24c supply session "
        "and admission consumers. Their existing symbolic models and reference "
        "codecs close none of the missing descriptor or lowering obligations.", "",
        "The inventory excludes declined grammars: 2G/3G/4G cellular state machines "
        "(R-12-041), USB tunnelling and general vendor messages (R-12-062), and "
        "runtime trusted text configuration (R-10-029). Raw bounded samples, "
        "ciphertext blocks and arithmetic codewords are not promoted to semantic "
        "parsers; their typed framing and metadata remain covered above. Build-host "
        "differential oracles remain outside the shipped-parser inventory.", "",
    ]
    return "\n".join(lines)
