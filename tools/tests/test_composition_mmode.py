# SPDX-License-Identifier: Apache-2.0
"""Whole retained M-mode bytes and explicit installed-mapping refusal controls."""

import hashlib
import json
import os
from collections.abc import Callable
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from tests.harness import Case, ensure
from tests.test_composition_products import CATALOG, _prepare
from tests.test_composition_staged import OUTPUT, _staged_sandbox
from vos import asm, boot_chain, chain_mmode, composer, composition_mmode, image
from vos import boot_handoff as handoff
from vos.cli import composer as cli

REPORT = "out/mmode-byte-export.json"


def _export(root: Path, output: str = REPORT) -> dict[str, Any]:
    return cast("dict[str, Any]", composition_mmode.export_mmode(root, OUTPUT, CATALOG, output))


def _refused(root: Path, action: Callable[[], object], phrase: str) -> None:
    target = root / REPORT
    target.write_bytes(b"prior useful export")
    try:
        action()
    except (OSError, ValueError) as error:
        ensure(phrase in str(error), str(error))
    else:
        raise AssertionError(f"expected export refusal: {phrase}")
    ensure(target.read_bytes() == b"prior useful export", "refusal preserves useful report")


def _complete_real_stage() -> None:
    with _staged_sandbox() as root:
        _prepare(root)
        retained = {path: path.read_bytes() for path in (root / boot_chain.STAGED).iterdir()}
        record = _export(root)
        ensure(set(record) == {"schema_version", "kind", "member", "source", "catalog", "bindings",
                              "compiler_provenance_status", "entry", "regions", "payload", "stack",
                              "harness_window", "installed_mapping", "production_admission",
                              "final_target_acceptance"}, "closed report root")
        regions = record["regions"]
        ensure(isinstance(regions, list), "region list")
        ensure([region["kind"] for region in regions] == ["text", "zero-gap", "initializer", "slot-tag"],
               "complete stage partitions text, zero gap, initialized data and normal-slot tag")
        payload = b"".join(bytes.fromhex(region["hex"]) for region in regions)
        f = handoff.chain_layout(root)
        signed = bytes.fromhex(json.loads((root / boot_chain.IMAGES).read_bytes())["images"]["mmode-a"])
        ensure(payload == signed[f["BOOT_HEADER_BYTES"]:], "exact complete authenticated payload bytes")
        ensure(record["entry"] == f["CHAIN_MMODE_LOAD_BASE"], "actual stage entry")
        for index, region in enumerate(regions):
            blob = bytes.fromhex(region["hex"])
            ensure(region["length"] == len(blob) and region["sha256"] == hashlib.sha256(blob).hexdigest(),
                   "every exported byte contributes to the recorded object identity")
            if index:
                prior = regions[index - 1]
                ensure(region["address"] == prior["address"] + prior["length"], "no unrecorded byte hole")
        ensure(not any(bytes.fromhex(regions[1]["hex"])), "explicit gap bytes are zero")
        ensure(bytes.fromhex(regions[-1]["hex"]) == b"VOSSLOTA", "normal slot-A tag")
        ensure(record["payload"] == {"address": f["CHAIN_MMODE_LOAD_BASE"], "length": len(payload),
                                      "sha256": hashlib.sha256(payload).hexdigest()}, "whole-payload binding")
        ensure(record["harness_window"] == {"address": f["CHAIN_MMODE_LOAD_BASE"],
                    "length": f["CHAIN_MMODE_REGION_BYTES"], "writable": True, "executable": True},
               "actual RWX window remains disclosed")
        ensure(record["installed_mapping"] == "unresolved-rwx-window"
               and record["production_admission"] is False and record["final_target_acceptance"] is False,
               "historical export supplies no installed representation or proof verdict")
        stack = record["stack"]
        ensure(isinstance(stack, dict) and stack["address"] >= f["CHAIN_MMODE_LOAD_BASE"] + len(payload)
               and stack["address"] + stack["length"] == f["CHAIN_MMODE_LOAD_BASE"] + f["CHAIN_MMODE_REGION_BYTES"],
               "external stack is inventoried separately from the retained payload")
        first = (root / REPORT).read_bytes()
        _export(root)
        ensure((root / REPORT).read_bytes() == first, "unchanged byte-identical export")
        ensure(all(path.read_bytes() == data for path, data in retained.items()), "historical bytes unchanged")


def _reconstruction_defects() -> None:
    original = chain_mmode.mmode_image
    for defect in ("text", "gap", "initializer", "truncation"):
        with _staged_sandbox() as root:
            _prepare(root)
            def changed(checkout: Path, stream: str, key: bytes, defect: str = defect) -> chain_mmode.Assembled:
                built = original(checkout, stream, key)
                at = handoff.chain_layout(checkout)["CHAIN_MMODE_DATA_AT"]
                payload = bytearray(built.payload)
                if defect == "truncation":
                    return replace(built, payload=bytes(payload[:-1]))
                position = {"text": 0, "gap": at - 1, "initializer": at}[defect]
                payload[position] ^= 1
                return replace(built, payload=bytes(payload))
            with patch.object(chain_mmode, "mmode_image", changed):
                _refused(root, lambda: _export(root), "complete retained slot-A payload")
    with _staged_sandbox() as root:
        _prepare(root)
        tags = chain_mmode.slot_tag_bytes(root)
        with patch.object(chain_mmode, "slot_tag_bytes", return_value=(b"VOSSLOTB", *tags[1:])):
            _refused(root, lambda: _export(root), "complete retained slot-A payload")


def _harness_defects() -> None:
    original = chain_mmode.compose_main
    for field, replacement in (("writable", False), ("executable", False), ("addr", 0)):
        with _staged_sandbox() as root:
            _prepare(root)
            def changed(checkout: Path, window: bytes, record: bytes, mailbox: bytes,
                        kernel_store: bytes, field: str = field,
                        replacement: bool | int = replacement) -> chain_mmode.Program:
                program = original(checkout, window, record, mailbox, kernel_store)
                mmode = next(section for section in program.sections if section.name == ".mmode")
                setattr(mmode, field, replacement)
                return program
            with patch.object(chain_mmode, "compose_main", changed):
                _refused(root, lambda: _export(root), "RWX permissions differ")


def _stale_inputs() -> None:
    for relative in ("firmware/chain/target/mmode.s", "firmware/chain/mmode.c", CATALOG):
        with _staged_sandbox() as root:
            _prepare(root)
            target = root / relative
            target.write_bytes(target.read_bytes() + b"\n")
            if relative == CATALOG:
                raw = json.loads(target.read_bytes())
                raw["production_admission"] = True
                target.write_bytes(composer.canonical_bytes(raw))
            _refused(root, lambda: _export(root), "catalog differs" if relative == CATALOG else "stale source binding")


def _publication_drift() -> None:
    original = composer.canonical_bytes
    for relative in ("tools/vos/chain_mmode.py", "firmware/chain/mmode_entry.s", CATALOG):
        with _staged_sandbox() as root:
            _prepare(root)
            def drift(value: object, relative: str = relative) -> bytes:
                encoded = original(value)
                if isinstance(value, dict) and value.get("kind") == "historical-mmode-byte-export":
                    target = root / relative
                    target.write_bytes(target.read_bytes() + b"\n")
                return encoded
            with patch.object(composer, "canonical_bytes", drift):
                _refused(root, lambda: _export(root), "stale source binding")


def _remaining_contract_boundaries() -> None:
    assemble = asm.Assembler.assemble
    construct = chain_mmode.mmode_image
    with _staged_sandbox() as root:
        _prepare(root)
        for defect in ("entry", "extent"):
            def changed(assembler: asm.Assembler, defect: str = defect) -> tuple[
                    list[image.Section], dict[str, tuple[str, int]], int]:
                sections, symbols, entry = assemble(assembler)
                if assembler.name == "export-retained-mmode":
                    if defect == "entry":
                        return sections, symbols, entry + 4
                    next(section for section in sections if section.name == ".data").addr += 8
                return sections, symbols, entry
            with patch.object(asm.Assembler, "assemble", changed):
                _refused(root, lambda: _export(root), "different entry" if defect == "entry" else "different extents")
        def wrong_root(checkout: Path, stream: str, key: bytes) -> chain_mmode.Assembled:
            return construct(checkout, stream, bytes([key[0] ^ 1]) + key[1:])
        with patch.object(chain_mmode, "mmode_image", wrong_root):
            _refused(root, lambda: _export(root), "complete retained slot-A payload")
        def drift(checkout: Path, stream: str, key: bytes) -> chain_mmode.Assembled:
            built = construct(checkout, stream, key)
            helper = checkout / "tools/vos/chain_mmode.py"
            helper.write_bytes(helper.read_bytes() + b"\n")
            return built
        with patch.object(chain_mmode, "mmode_image", drift):
            _refused(root, lambda: _export(root), "stale source binding")
    with _staged_sandbox() as root:
        _prepare(root)
        (root / "firmware/chain/target/mmode.s").unlink()
        _refused(root, lambda: _export(root), "mmode.s")

def _aliases_and_cli() -> None:
    with _staged_sandbox() as root:
        _prepare(root)
        os.link(root / "firmware/chain/target/mmode.s", root / REPORT)
        original = (root / REPORT).read_bytes()
        try:
            _export(root)
        except ValueError as error:
            ensure("overwrite an input" in str(error), str(error))
        else:
            raise AssertionError("hardlinked output accepted")
        ensure((root / REPORT).read_bytes() == original, "input alias preserved")
        (root / REPORT).unlink()
        output = StringIO()
        with patch.object(cli.corpus, "find_root", return_value=root), redirect_stdout(output):
            code = cli.main(["export-staged-mmode", OUTPUT, "--products", CATALOG, "--output", REPORT])
        ensure(code == 0, output.getvalue())
        ensure(json.loads(output.getvalue())["member"] == "mmode-firmware", "actual public command")


def cases() -> list[Case]:
    return [Case("complete-real-stage-byte-export", _complete_real_stage),
            Case("text-gap-initializer-payload-and-tag-defects", _reconstruction_defects),
            Case("actual-harness-permissions-and-placement", _harness_defects),
            Case("stale-source-product-and-catalog", _stale_inputs),
            Case("publication-helper-entry-and-catalog-drift", _publication_drift),
            Case("entry-extent-root-missing-unit-and-reconstruction-drift", _remaining_contract_boundaries),
            Case("hardlink-preservation-and-public-command", _aliases_and_cli)]
