# SPDX-License-Identifier: Apache-2.0
"""Refusal boundaries for the inventory's source-accounting claim.

These are mutations of the actual reviewed inventory, not a second miniature
inventory maintained by the tests. Every write stays under this checkout's out/.
"""

import json
import tempfile
from collections.abc import Callable, Generator
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any

from tests.harness import Case, ensure
from vos import wire_formats as formats

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def _fixture() -> Generator[tuple[Path, dict[str, Any]]]:
    source: dict[str, Any] = json.loads((ROOT / formats.SOURCE).read_text(encoding="utf-8"))
    paths = {formats.SOURCE, formats.SCHEMA, formats.CROWN, formats.REGISTER,
             "docs/assurance/unassigned-proof-map.md",
             "PLAN.md"}
    for entry in source["entries"]:
        paths.update(ref.split("#", 1)[0] for ref in entry["references"])
        if entry["members_from"] is not None:
            paths.add(entry["members_from"]["path"])
    paths.update(path.relative_to(ROOT).as_posix() for path in (ROOT / "proofs").rglob("*.v"))
    scratch = ROOT / "out" / "wire-format-tests"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        root = Path(temporary)
        for relative in paths:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / relative).read_bytes())
        yield root, source


def _write(root: Path, source: dict[str, Any]) -> None:
    (root / formats.SOURCE).write_text(json.dumps(source), encoding="utf-8", newline="")


def _refused(root: Path, message: str) -> None:
    try:
        formats.emit(root)
    except formats.InventoryError as exc:
        ensure(message in str(exc), f"wrong refusal: {exc}; expected {message}")
        return
    raise AssertionError(f"inventory accepted mutation requiring: {message}")


def _mutated(change: Callable[[dict[str, Any]], None], message: str) -> None:
    with _fixture() as (root, source):
        change(source)
        _write(root, source)
        _refused(root, message)


def _reviewed_inventory() -> None:
    rendered = formats.emit(ROOT)
    entries = formats.load(ROOT)
    ensure(all(entry.owner for entry in entries), "an owner is not explicit")
    ensure("manifest_has_one_admissible_encoding" in rendered,
           "the real reference-codec theorem disappeared")
    ensure("reference codec only" in rendered and "Descriptor: **absent**" in rendered,
           "reference codecs were not distinguished from descriptors")
    ensure(rendered == (ROOT / formats.ARTIFACT).read_text(encoding="utf-8"),
           "tracked inventory differs from its generator")


def _missing_class() -> None:
    def change(source: dict[str, Any]) -> None:
        source["entries"] = [entry for entry in source["entries"] if "x509" not in entry["classes"]]
    _mutated(change, "unrepresented row 10 classes")


def _blank_owner() -> None:
    def change(source: dict[str, Any]) -> None:
        source["entries"][0]["owner"] = ""
    _mutated(change, ".owner")


def _unknown_owner() -> None:
    def change(source: dict[str, Any]) -> None:
        source["entries"][0]["owner"] = "U-99999"
    _mutated(change, "is not a landed work item")


def _ordinary_prose_is_not_an_owner() -> None:
    def change(source: dict[str, Any]) -> None:
        source["entries"][0]["owner"] = "the"
    _mutated(change, "is not a landed work item")


def _forged_descriptor() -> None:
    def change(source: dict[str, Any]) -> None:
        source["entries"][0]["descriptor"] = "proved"
    _mutated(change, ".descriptor")


def _missing_symbol() -> None:
    def change(source: dict[str, Any]) -> None:
        source["entries"][0]["references"] = ["proofs/ModuleFormats.v#unwritten_canonicity"]
    _mutated(change, "missing proof symbol")


def _unlisted_library_use() -> None:
    with _fixture() as (root, _):
        (root / "proofs" / "Unlisted.v").write_text(
            "From Narcissus Require Import Formats.\nDefinition unlisted := 0.\n",
            encoding="utf-8", newline="")
        _refused(root, "Narcissus use requires descriptor bindings")


def _library_use_beside_a_comment_refuses() -> None:
    # A blanked comment separates words, so a name a comment sets off is still read.
    with _fixture() as (root, _):
        (root / "proofs" / "Beside.v").write_text(
            "From(* the library *)Narcissus Require Import Formats.\n",
            encoding="utf-8", newline="")
        _refused(root, "Beside.v: Narcissus use requires descriptor bindings")


def _referenced_source_library_use_refuses() -> None:
    # A source an entry references is read once for both its symbols and the absence
    # scan, and the scan still reads what was added to it.
    with _fixture() as (root, _):
        path = root / "proofs" / "ModuleFormats.v"
        path.write_text(path.read_text(encoding="utf-8")
                        + "\nFrom Narcissus Require Import Formats.\n",
                        encoding="utf-8", newline="")
        _refused(root, "ModuleFormats.v: Narcissus use requires descriptor bindings")


def _comments_are_not_descriptors() -> None:
    with _fixture() as (root, _):
        (root / "proofs" / "Comment.v").write_text(
            "(* Narcissus (* CorrectDecoder *) remains open. *)\nDefinition x := 0.\n",
            encoding="utf-8", newline="")
        formats.emit(root)


def _changed_crown_membership() -> None:
    with _fixture() as (root, _):
        path = root / formats.CROWN
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("the USB grammars", "the USB and new-device grammars"),
                        encoding="utf-8", newline="")
        _refused(root, "row 10 membership changed")


def _new_grammar_form_is_rendered() -> None:
    with _fixture() as (root, _):
        path = root / "docs/hardware/immutable-module-contract.md"
        text = path.read_text(encoding="utf-8")
        needle = "| `ID-RECORD` |"
        ensure(needle in text, "test cannot find the owning grammar table")
        path.write_text(text.replace(needle,
                        "| `NEW-RECORD` | module to host | reserved | bounded |\n" + needle, 1),
                        encoding="utf-8", newline="")
        ensure("`NEW-RECORD`" in formats.emit(root), "new grammar form disappeared from the view")


def _missing_grammar_table() -> None:
    with _fixture() as (root, _):
        path = root / "docs/hardware/ensemble-link-contract.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("### 1.2 The four forms, and what selects between them",
                                     "### Renamed without inventory maintenance"),
                        encoding="utf-8", newline="")
        _refused(root, "member-table heading changed")


def _unquoted_grammar_member_cannot_disappear() -> None:
    with _fixture() as (root, _):
        path = root / "docs/hardware/immutable-module-contract.md"
        text = path.read_text(encoding="utf-8")
        needle = "| `ID-RECORD` |"
        ensure(needle in text, "test cannot find the owning grammar table")
        path.write_text(text.replace(needle,
                        "| NEW-RECORD | module to host | reserved | bounded |\n" + needle, 1),
                        encoding="utf-8", newline="")
        _refused(root, "unsupported grammar member row")


def _nas_exception_cannot_disappear() -> None:
    def change(source: dict[str, Any]) -> None:
        next(entry for entry in source["entries"] if entry["id"] == "fiveg-nas")[
            "transcription"] = "none authored"
    _mutated(change, "NAS exception must be explicitly and exclusively flagged")


def _duplicate_entry() -> None:
    def change(source: dict[str, Any]) -> None:
        source["entries"].append(source["entries"][0])
    _mutated(change, "duplicate entry id")


def _unsafe_reference() -> None:
    def change(source: dict[str, Any]) -> None:
        source["entries"][0]["references"] = ["../external.v"]
    _mutated(change, "unsafe repository path")


def _missing_idl_mapping() -> None:
    def change(source: dict[str, Any]) -> None:
        source["entries"] = [entry for entry in source["entries"] if entry["id"] != "idl-mapping"]
    _mutated(change, "IDL wire-format mapping is unrepresented")


def _declaration_schema_refusals() -> None:
    with _fixture() as (root, original):
        mutations: list[object] = [None, [], dict(original, schema=True),
                                   dict(original, schema=1.0), dict(original, extra="unread")]
        for key in original:
            missing = deepcopy(original)
            del missing[key]
            mutations.append(missing)
        for field, value in (("id", "name\n"), ("id", "Upper"), ("name", " "),
                             ("classes", ["rrc", "rrc"]), ("classes", None),
                             ("requirements", []), ("requirements", ["R-05-042\n"]),
                             ("requirements", ["R-05-042", "R-05-042"]),
                             ("owner", "line\nbreak"), ("canonicity", "bad|pipe"),
                             ("evidence", True), ("references", [1]),
                             ("references", ["proofs/ModuleFormats.v"] * 2),
                             ("transcription", "unknown"), ("members_from", {}),
                             ("members_from", {"path": "a", "heading": "b", "until": "c", "extra": 1}),
                             ("extra", "unread")):
            changed = deepcopy(original)
            changed["entries"][0][field] = value
            mutations.append(changed)
        for mutation in mutations:
            (root / formats.SOURCE).write_text(json.dumps(mutation), encoding="utf-8")
            _refused(root, Path(formats.SCHEMA).name)
        _write(root, original)
        data = (root / formats.SOURCE).read_text(encoding="utf-8")
        (root / formats.SOURCE).write_text(data.replace('"schema": 1', '"schema": 1, "schema": 1', 1),
                                          encoding="utf-8")
        _refused(root, "duplicate JSON key")


def _missing_or_malformed_schema_refuses() -> None:
    with _fixture() as (root, _):
        (root / formats.SCHEMA).unlink()
        _refused(root, "cannot read a valid schema")
        for invalid in ('{"type": 17}', '{"type": "object", "type": "object"}',
                        '{"$ref": "https://example.invalid/unfetched.json"}'):
            (root / formats.SCHEMA).write_text(invalid, encoding="utf-8")
            _refused(root, "cannot read a valid schema")


def cases() -> list[Case]:
    return [Case("reviewed inventory reproduces", _reviewed_inventory),
            Case("row 10 class cannot disappear", _missing_class),
            Case("blank owner refuses", _blank_owner),
            Case("unknown owner refuses", _unknown_owner),
            Case("ordinary prose is not an owner", _ordinary_prose_is_not_an_owner),
            Case("reference cannot become a descriptor", _forged_descriptor),
            Case("missing theorem refuses", _missing_symbol),
            Case("unlisted library use refuses", _unlisted_library_use),
            Case("library use beside a comment refuses", _library_use_beside_a_comment_refuses),
            Case("referenced source library use refuses", _referenced_source_library_use_refuses),
            Case("nested comments are not proof evidence", _comments_are_not_descriptors),
            Case("changed crown membership needs review", _changed_crown_membership),
            Case("new owning grammar form reaches the view", _new_grammar_form_is_rendered),
            Case("lost grammar heading refuses", _missing_grammar_table),
            Case("unquoted grammar member cannot disappear", _unquoted_grammar_member_cannot_disappear),
            Case("NAS flag remains explicit", _nas_exception_cannot_disappear),
            Case("duplicate entry refuses", _duplicate_entry),
            Case("unsafe reference refuses", _unsafe_reference),
            Case("IDL mapping cannot disappear", _missing_idl_mapping),
            Case("declaration schema refuses malformed inputs", _declaration_schema_refusals),
            Case("missing or malformed schema refuses", _missing_or_malformed_schema_refuses)]
