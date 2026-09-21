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
from typing import Any

from vos import proofs

SOURCE = "interfaces/wire-formats.json"
ARTIFACT = "docs/assurance/wire-format-inventory.md"
CROWN = "docs/assurance/crown-jewels.md"
REGISTER = "docs/requirements-register.md"
REQUIRED_CLASSES = frozenset({
    "rrc", "mlme", "nas", "usb", "image", "media", "font", "archive",
    "document", "pack", "manifest", "x509", "module-manifest",
    "module-certificate", "module-endorsement", "module-message", "ensemble",
})
_ID = re.compile(r"[a-z][a-z0-9-]*\Z")
_REQUIREMENT = re.compile(r"R-\d+-\d+[a-z]*\Z")
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


def _object(raw: object, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != keys:
        raise InventoryError(f"{where}: expected exactly {sorted(keys)}")
    return raw


def _text(raw: object, where: str) -> str:
    if not isinstance(raw, str) or not raw.strip() or any(c in raw for c in "\r\n|"):
        raise InventoryError(f"{where}: expected nonempty single-line text without pipes")
    return raw


def _strings(raw: object, where: str, *, empty: bool = False) -> tuple[str, ...]:
    if not isinstance(raw, list) or (not raw and not empty):
        raise InventoryError(f"{where}: expected a {'possibly empty ' if empty else ''}list")
    result = tuple(_text(item, where) for item in raw)
    if len(set(result)) != len(result):
        raise InventoryError(f"{where}: duplicate members")
    return result


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


def _table_members(root: Path, raw: object) -> tuple[str, ...]:
    if raw is None:
        return ()
    table = _object(raw, {"path", "heading", "until"}, "member table")
    path = _text(table["path"], "member table path")
    heading = _text(table["heading"], "member table heading")
    until = _text(table["until"], "member table end")
    source = _read(root, path)
    if source.count(heading) != 1:
        raise InventoryError(f"{path}: member-table heading changed")
    tail = source.split(heading, 1)[1]
    if until not in tail:
        raise InventoryError(f"{path}: member-table end changed")
    section = tail.split(until, 1)[0]
    members = tuple(_text(match.group(1), "grammar member") for line in section.splitlines()
                    if (match := re.match(r"\| `([^`]+)` \|", line)))
    if not members or len(set(members)) != len(members):
        raise InventoryError(f"{path}: empty or duplicated member table")
    return members


def load(root: Path) -> tuple[Entry, ...]:
    """Validate the source, live member tables and the current descriptor absence."""
    try:
        raw = json.loads(_read(root, SOURCE))
    except ValueError as exc:
        raise InventoryError(f"{SOURCE}: {exc}") from exc
    data = _object(raw, {"schema", "reviewed_row10_sha256", "classes", "entries"}, SOURCE)
    if type(data["schema"]) is not int or data["schema"] != 1:
        raise InventoryError("unsupported wire-format inventory schema")
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
    if not isinstance(classes, dict) or set(classes) != REQUIRED_CLASSES:
        raise InventoryError("row 10 member-class coverage set changed or is incomplete")
    for key, phrase in classes.items():
        if _text(phrase, key) not in specification:
            raise InventoryError(f"class {key}: source phrase absent from row 10")
    if not isinstance(data["entries"], list) or not data["entries"]:
        raise InventoryError("the inventory has no entries")
    register = _read(root, REGISTER)
    owner_text = _read(root, "docs/assurance/unassigned-proof-map.md") + _read(
        root, "docs/implementation/implementation-checklist.md")
    entries: list[Entry] = []
    seen: set[str] = set()
    covered: set[str] = set()
    for item in data["entries"]:
        entry = _object(item, {
            "id", "name", "classes", "requirements", "owner", "descriptor",
            "transcription", "canonicity", "evidence", "references", "members_from",
        }, "format entry")
        key = _text(entry["id"], "entry id")
        if not _ID.fullmatch(key) or key in seen:
            raise InventoryError(f"invalid or duplicate entry id: {key}")
        seen.add(key)
        if entry["descriptor"] != "absent":
            raise InventoryError(f"{key}: schema 1 cannot credit a Narcissus descriptor")
        memberships = _strings(entry["classes"], key, empty=True)
        if set(memberships) - REQUIRED_CLASSES:
            raise InventoryError(f"{key}: unknown member class")
        covered.update(memberships)
        requirements = _strings(entry["requirements"], key)
        for requirement in requirements:
            if not _REQUIREMENT.fullmatch(requirement) or f"**{requirement}**" not in register:
                raise InventoryError(f"{key}: unknown requirement {requirement}")
        owner = _text(entry["owner"], key)
        if owner != "none" and re.search(r"(?<![\w-])" + re.escape(owner)
                                         + r"(?![\w-])", owner_text) is None:
            raise InventoryError(f"{key}: owner {owner} is not a landed work item")
        references = _strings(entry["references"], key, empty=True)
        for reference in references:
            path, separator, symbol = reference.partition("#")
            source = _read(root, path)
            if separator and (not path.endswith(".v") or not re.search(
                        r"\b(?:Definition|Fixpoint|Record|Inductive|Theorem|Lemma)\s+"
                        + re.escape(symbol) + r"\b", proofs.strip_comments(source))):
                raise InventoryError(f"{key}: missing proof symbol {reference}")
        transcription = _text(entry["transcription"], key)
        if transcription not in {"none authored", "NAS grammar required", "reference codec only"}:
            raise InventoryError(f"{key}: unsupported hand-transcription flag")
        if (transcription == "NAS grammar required") != ("nas" in memberships):
            raise InventoryError(f"{key}: NAS exception must be explicitly and exclusively flagged")
        entries.append(Entry(key, _text(entry["name"], key), memberships, requirements,
                             owner, transcription, _text(entry["canonicity"], key),
                             _text(entry["evidence"], key), references,
                             _table_members(root, entry["members_from"])))
    if REQUIRED_CLASSES - covered:
        raise InventoryError(f"unrepresented row 10 classes: {sorted(REQUIRED_CLASSES - covered)}")
    if "idl-mapping" not in seen:
        raise InventoryError("row 3's IDL wire-format mapping is unrepresented")
    sources = sorted((root / "proofs").rglob("*.v"))
    if not sources:
        raise InventoryError("no proof sources: descriptor absence cannot be inspected")
    for source in sources:
        code = proofs.strip_comments(_read(root, source.relative_to(root).as_posix()))
        # A new library use is a finding, including support modules. It cannot hide
        # behind the old empty inventory. Alias/load-path conventions need review
        # when U-13 selects an import path; no general Rocq semantic scan is claimed.
        if _NARCISSUS.search(code):
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
