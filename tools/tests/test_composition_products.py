# SPDX-License-Identifier: Apache-2.0
"""Actual retained firmware stages through replayed production product selection."""

import json
import os
from collections.abc import Callable
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from tests.test_composition_staged import OUTPUT, _staged_sandbox
from vos import composer
from vos import composition as c
from vos import composition_staged as staged
from vos.cli import composer as cli

CATALOG = "out/boot-products.json"
MMODE = "firmware/chain/target/mmode.s"


def _prepare(root: Path) -> None:
    staged.bind_boot_chain(root, c.EXAMPLE, OUTPUT)
    staged.export_boot_products(root, OUTPUT, CATALOG)


def _refused(action: Callable[[], object], phrase: str) -> None:
    try:
        action()
    except ValueError as error:
        ensure(phrase in str(error), str(error))
    else:
        raise AssertionError(f"expected product selection refusal: {phrase}")


def _select(root: Path, slot: str = "mmode-firmware-artifact", unit: str = "mmode",
            artifact: str = MMODE) -> dict[str, object]:
    return staged.select_boot_product(root, OUTPUT, CATALOG, slot, unit, artifact)


def _real_consumer() -> None:
    with _staged_sandbox() as root:
        _prepare(root)
        selected = _select(root)
        ensure(selected["member"] == "mmode-firmware" and selected["artifact_slot"] == "mmode-firmware-artifact",
               "actual M-mode stage resolves its own runtime slot")
        ensure(selected["source"] == c.reference(root, MMODE) and selected["artifact"] == c.reference(root, MMODE),
               "selection consumes the independently expected actual normal M-mode bytes")
        catalog = json.loads((root / CATALOG).read_bytes())
        ensure(catalog["products"] == [
            {"member": "rot-firmware", "artifact_slot": "rot-firmware-artifact", "units": [
                {"unit": "rom", "source": c.reference(root, "firmware/chain/target/rom.s")},
                {"unit": "runtime", "source": c.reference(root, "firmware/chain/target/runtime.s")}]},
            {"member": "mmode-firmware", "artifact_slot": "mmode-firmware-artifact", "units": [
                {"unit": "mmode", "source": c.reference(root, MMODE)}]}],
            "RoT stages stay distinct and normal stage membership is independently expected")
        copy = "out/consumer-mmode.s"
        (root / copy).write_bytes((root / MMODE).read_bytes())
        ensure(_select(root, artifact=copy)["artifact"] == c.reference(root, copy),
               "consumer may retain its own distinct file with the selected bytes")
        outputs = c.projections(root, OUTPUT)
        members = json.loads(outputs["recipe-members.json"])["payload"]["members"]
        member = next(entry for entry in members if entry["id"] == "mmode-firmware")
        ensure(member["artifact_slot"] == selected["artifact_slot"] and selected["source"] in member["sources"],
               "ordinary production projection carries the same selected source and symbolic slot")
        ensure(member["status"] == "partial" and member["placement"] is None,
               "retained stage selection cannot promote the incomplete roster")
        ensure(selected["production_admission"] is False and selected["final_target_acceptance"] is False,
               "consumer retains the exact historical comparison scope")
        _refused(lambda: c.build_record(root, OUTPUT, outputs,
                                       {"mmode-firmware-artifact": c.reference(root, copy)},
                                       c.reference(root, copy), b""), "missing graph binding")


def _selection_refusals() -> None:
    with _staged_sandbox() as root:
        _prepare(root)
        for slot, unit, artifact, phrase in (
                ("storage-artifact", "mmode", MMODE, "unknown artifact slot"),
                ("mmode-firmware-artifact", "rom", MMODE, "unit outside its artifact slot"),
                ("rot-firmware-artifact", "mmode", MMODE, "unit outside its artifact slot"),
                ("mmode-firmware-artifact", "mmode", "firmware/chain/target/runtime.s", "differs from its selected unit")):
            _refused(lambda slot=slot, unit=unit, artifact=artifact: _select(root, slot, unit, artifact), phrase)
        (root / "out/substituted.s").write_bytes((root / MMODE).read_bytes() + b"\n")
        _refused(lambda: _select(root, artifact="out/substituted.s"), "differs from its selected unit")
        ensure(_select(root)["member"] == "mmode-firmware", "refusals do not disturb valid selection")


def _catalog_replay() -> None:
    with _staged_sandbox() as root:
        _prepare(root)
        original = (root / CATALOG).read_bytes()
        for key, value in (("schema_version", True), ("schema_version", 1.0),
                           ("production_admission", 0), ("final_target_acceptance", 0.0)):
            changed = json.loads(original)
            changed[key] = value
            (root / CATALOG).write_bytes(composer.canonical_bytes(changed))
            _refused(lambda: _select(root), "catalog differs from inspected candidate")
        raw = json.loads(original)
        raw["products"][1]["units"][0]["source"] = c.reference(root, "firmware/chain/target/runtime.s")
        (root / CATALOG).write_bytes(composer.canonical_bytes(raw))
        _refused(lambda: _select(root), "catalog differs from inspected candidate")
        (root / CATALOG).write_bytes(original)
        candidate = json.loads((root / OUTPUT).read_bytes())
        next(member for member in candidate["members"] if member["id"] == "storage")["producer"] = staged.PRODUCER
        (root / OUTPUT).write_bytes(composer.canonical_bytes(candidate))
        _refused(lambda: _select(root), "producer claims another member")


def _selection_drift() -> None:
    artifact = "out/consumer-mmode.s"
    reference = c.reference
    for relative in (artifact, OUTPUT, CATALOG, MMODE, "firmware/chain/mmode.c"):
        with _staged_sandbox() as root:
            _prepare(root)
            (root / artifact).write_bytes((root / MMODE).read_bytes())
            def drift(checkout: Path, path: str, changed: str = relative) -> dict[str, str]:
                result = reference(checkout, path)
                if path == artifact:
                    target = checkout / changed
                    target.write_bytes(target.read_bytes() + b"\n")
                return result

            with patch.object(c, "reference", drift):
                _refused(lambda: _select(root, artifact=artifact), "stale source binding")


def _inspection_refusals() -> None:
    for relative in (MMODE, "firmware/chain/mmode.c"):
        with _staged_sandbox() as root:
            _prepare(root)
            original = (root / CATALOG).read_bytes()
            target = root / relative
            target.write_bytes(target.read_bytes() + b"\n")
            _refused(lambda: _select(root), "stale source binding")
            _refused(lambda: staged.export_boot_products(root, OUTPUT, CATALOG), "stale source binding")
            ensure((root / CATALOG).read_bytes() == original, "inspection refusal preserves the prior catalog")


def _catalog_alias() -> None:
    with _staged_sandbox() as root:
        staged.bind_boot_chain(root, c.EXAMPLE, OUTPUT)
        original = (root / OUTPUT).read_bytes()
        os.link(root / OUTPUT, root / CATALOG)
        _refused(lambda: staged.export_boot_products(root, OUTPUT, CATALOG), "overwrite an input or product")
        ensure((root / OUTPUT).read_bytes() == original, "catalog publication cannot overwrite its candidate")


def _direct_reference(root: Path, source: str, field: str) -> str:
    extra = "out/direct-input.s"
    (root / extra).parent.mkdir(parents=True, exist_ok=True)
    (root / extra).write_bytes(b"independent direct member input\n")
    raw = json.loads((root / source).read_bytes())
    member = next(entry for entry in raw["members"] if entry["id"] == "mmode-firmware")
    if field == "sources":
        member["sources"].append(c.reference(root, extra))
    else:
        member["derivation"]["source"] = c.reference(root, extra)
    (root / source).write_bytes(composer.canonical_bytes(raw))
    return extra


def _direct_publication_aliases() -> None:
    for operation in ("candidate", "catalog"):
        for field in ("sources", "derivation"):
            for linked in (False, True):
                with _staged_sandbox() as root:
                    if operation == "catalog":
                        staged.bind_boot_chain(root, c.EXAMPLE, OUTPUT)
                    source = c.EXAMPLE if operation == "candidate" else OUTPUT
                    extra = _direct_reference(root, source, field)
                    target = "out/direct-alias.s" if linked else extra
                    if linked:
                        os.link(root / extra, root / target)
                    original = (root / extra).read_bytes()
                    action = staged.bind_boot_chain if operation == "candidate" else staged.export_boot_products
                    _refused(lambda action=action, source=source, target=target: action(root, source, target),
                             "overwrite an input or product")
                    ensure((root / extra).read_bytes() == original and (root / target).read_bytes() == original,
                           "direct member and derivation alias refusals preserve consumed bytes")


def _direct_selection_drift() -> None:
    artifact = "out/consumer-mmode.s"
    reference = c.reference
    for field in ("sources", "derivation"):
        with _staged_sandbox() as root:
            staged.bind_boot_chain(root, c.EXAMPLE, OUTPUT)
            extra = _direct_reference(root, OUTPUT, field)
            staged.export_boot_products(root, OUTPUT, CATALOG)
            (root / artifact).write_bytes((root / MMODE).read_bytes())

            def drift(checkout: Path, path: str, changed: str = extra) -> dict[str, str]:
                result = reference(checkout, path)
                if path == artifact:
                    target = checkout / changed
                    target.write_bytes(target.read_bytes() + b"\n")
                return result

            with patch.object(c, "reference", drift):
                _refused(lambda: _select(root, artifact=artifact), "stale source binding")


def _cli_consumer() -> None:
    with _staged_sandbox() as root:
        staged.bind_boot_chain(root, c.EXAMPLE, OUTPUT)
        for arguments in (
                ["export-staged-boot-products", OUTPUT, "--output", CATALOG],
                ["check-staged-boot-product", OUTPUT, "--products", CATALOG,
                 "--slot", "mmode-firmware-artifact", "--unit", "mmode", "--artifact", MMODE]):
            output = StringIO()
            with patch.object(cli.corpus, "find_root", return_value=root), redirect_stdout(output):
                code = cli.main(arguments)
            ensure(code == 0, output.getvalue())
            result = json.loads(output.getvalue())
            ensure(result["final_target_acceptance"] is False and result["production_admission"] is False,
                   "public producer and consumer preserve open acceptance")


def cases() -> list[Case]:
    return [Case("actual-retained-product-consumer", _real_consumer),
            Case("wrong-slot-stage-and-byte-substitution", _selection_refusals),
            Case("catalog-and-candidate-replay", _catalog_replay),
            Case("selection-publication-boundary-drift", _selection_drift),
            Case("stale-retained-producer-refusal", _inspection_refusals),
            Case("catalog-input-alias-refusal", _catalog_alias),
            Case("direct-member-and-derivation-publication-alias", _direct_publication_aliases),
            Case("direct-member-and-derivation-selection-drift", _direct_selection_drift),
            Case("public-retained-product-consumer", _cli_consumer)]
