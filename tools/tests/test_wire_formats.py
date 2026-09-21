# SPDX-License-Identifier: Apache-2.0
"""Refusal boundaries for the inventory's source-accounting claim.

These are mutations of the actual reviewed inventory, not a second miniature
inventory maintained by the tests. Every write stays under this checkout's out/.
"""

import json
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from tests.harness import Case, ensure
from vos import wire_formats as formats

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def _fixture() -> Iterator[tuple[Path, dict[str, Any]]]:
    source: dict[str, Any] = json.loads((ROOT / formats.SOURCE).read_text(encoding="utf-8"))
    paths = {formats.SOURCE, formats.CROWN, formats.REGISTER,
             "docs/assurance/unassigned-proof-map.md",
             "docs/implementation/implementation-checklist.md"}
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
    _mutated(change, "nonempty single-line text")


def _unknown_owner() -> None:
    def change(source: dict[str, Any]) -> None:
        source["entries"][0]["owner"] = "U-99999"
    _mutated(change, "is not a landed work item")


def _forged_descriptor() -> None:
    def change(source: dict[str, Any]) -> None:
        source["entries"][0]["descriptor"] = "proved"
    _mutated(change, "cannot credit a Narcissus descriptor")


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


def cases() -> list[Case]:
    return [Case("reviewed inventory reproduces", _reviewed_inventory),
            Case("row 10 class cannot disappear", _missing_class),
            Case("blank owner refuses", _blank_owner),
            Case("unknown owner refuses", _unknown_owner),
            Case("reference cannot become a descriptor", _forged_descriptor),
            Case("missing theorem refuses", _missing_symbol),
            Case("unlisted library use refuses", _unlisted_library_use),
            Case("nested comments are not proof evidence", _comments_are_not_descriptors),
            Case("changed crown membership needs review", _changed_crown_membership),
            Case("new owning grammar form reaches the view", _new_grammar_form_is_rendered),
            Case("lost grammar heading refuses", _missing_grammar_table),
            Case("NAS flag remains explicit", _nas_exception_cannot_disappear),
            Case("duplicate entry refuses", _duplicate_entry),
            Case("unsafe reference refuses", _unsafe_reference),
            Case("IDL mapping cannot disappear", _missing_idl_mapping)]
