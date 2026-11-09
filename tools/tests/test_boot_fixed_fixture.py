# SPDX-License-Identifier: Apache-2.0
"""One real package construction feeds two translated observer recipes."""

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from tests import test_boot_fixed
from tests.harness import TOOLS, Case, ensure
from vos import asm, fixed_boot_fixture, fixed_composition, image, package_artifacts


def fixture_sources(root: Path) -> None:
    for relative in (*fixed_boot_fixture.SOURCES, fixed_boot_fixture.CONFIGURATION):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TOOLS.parent / relative, path)


def _construction_once() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-fixed-boot-construction-") as directory:
        root = Path(directory)
        fixture_sources(root)
        original = asm.Assembler.assemble
        count = 0

        def counted(assembler: asm.Assembler) -> tuple[list[image.Section], dict[str, tuple[str, int]], int]:
            nonlocal count
            count += 1
            return original(assembler)

        with patch.object(asm.Assembler, "assemble", new=counted):
            record = fixed_boot_fixture.prepare(root)
        ensure(count == len(fixed_boot_fixture.SOURCES), "fixture reassembled a package for its second layout")
        layouts = cast("list[dict[str, Any]]", record["layouts"])
        packages = cast("list[dict[str, Any]]", record["packages"])
        expected = [member["artifact"] for member in packages]
        for member in packages:
            produced = member["producer_image"]
            ensure(package_artifacts.digest((root / produced["path"]).read_bytes()) == produced["sha256"]
                   and produced["base"] == fixed_boot_fixture.BASE,
                   "fixture discarded the exact produced-image binding")
        with patch.object(asm.Assembler, "assemble", side_effect=AssertionError("producer reran")):
            for layout in layouts:
                checked = fixed_composition.validate(root, layout["composition"], packages[0]["store"],
                                                     layout["image"])
                ensure([item["artifact"] for item in cast("list[dict[str, Any]]", checked["packages"])] == expected,
                       "translated layout selected different constructed artifacts")
                fixed_composition.compose(root, layout["composition"], packages[0]["store"],
                                          f"out/recomposed-{layout['name']}.elf")
                ensure((root / f"out/recomposed-{layout['name']}.elf").read_bytes()
                       == (root / layout["image"]).read_bytes(), "unchanged composition changed image bytes")
        ensure(record["production_admission"] is False and record["final_target_acceptance"] is False
               and record["roster_identity"] is None, "fixture advertised production evidence")
        for source in cast("list[dict[str, Any]]", record["source_identities"]):
            ensure(package_artifacts.digest((root / source["path"]).read_bytes()) == source["sha256"],
                   "fixture source identity is not the consumed bytes")
        ensure(json.loads((root / "out/fixed-boot-fixture/fixture.json").read_bytes()) == record,
               "saved construction record differs")


def _translated_observation_and_missing_peer() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-fixed-boot-layouts-") as directory:
        root = Path(directory)
        fixture_sources(root)
        record = fixed_boot_fixture.prepare(root)
        (root / "simulator.py").write_text(test_boot_fixed.PROGRAM, encoding="utf-8")
        with patch.object(asm.Assembler, "assemble", side_effect=AssertionError("producer reran")):
            for layout in cast("list[dict[str, Any]]", record["layouts"]):
                base, tohost = layout["base"], layout["tohost"]
                lines = [f"I 0 {base:016x} 00000013",
                         f"I 1 {base + fixed_boot_fixture.PEER_OFFSET:016x} 00000013",
                         f"W {tohost:X} 8 0 0101000000000046",
                         f"W {tohost:X} 8 0 0000000000000001", "SUCCESS"]
                recipe = layout["observation_recipe"]
                captured = test_boot_fixed._run(root, refresh=True, recipe_path=recipe,
                                                plan={"console": "F", "lines": lines})
                replay = test_boot_fixed._run(root, recipe_path=recipe, plan={"console": "F", "lines": lines})
                ensure(captured["findings"] == replay["findings"] == [],
                       f"translated fixture failed capture/replay: {captured}, {replay}")
                before = (root / recipe).read_bytes()
                absent = test_boot_fixed._run(root, refresh=True, recipe_path=recipe,
                                              plan={"console": "F", "lines": [lines[0], *lines[2:]]})
                ensure(any("fixture-worker" in item and "never entered" in item for item in absent["findings"]),
                       "HTIF success concealed the missing worker")
                ensure(absent["refreshed"] is False and (root / recipe).read_bytes() == before,
                       "missing-worker run replaced reviewed expectations")


def _fresh_output_and_source_drift() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-fixed-boot-preparation-refusals-") as directory:
        root = Path(directory)
        fixture_sources(root)
        for output in ("../outside", "tools/fixture", "out"):
            try:
                fixed_boot_fixture.prepare(root, output)
            except package_artifacts.PackageError:
                pass
            else:
                raise AssertionError(f"fixture accepted invalid output {output}")
        destination = root / "out/existing"
        destination.mkdir(parents=True)
        (destination / "useful").write_bytes(b"keep")
        try:
            fixed_boot_fixture.prepare(root, "out/existing")
        except package_artifacts.PackageError as error:
            ensure("fresh" in str(error), str(error))
        else:
            raise AssertionError("fixture overwrote an existing output directory")
        ensure((destination / "useful").read_bytes() == b"keep", "output refusal changed existing evidence")
        original = fixed_boot_fixture._package

        def drift(checkout: Path, output: Path, source: str, snapshot: bytes,
                  context: dict[str, str], *, controller: bool) -> dict[str, Any]:
            result = original(checkout, output, source, snapshot, context, controller=controller)
            path = root / fixed_boot_fixture.CONFIGURATION
            path.write_bytes(path.read_bytes() + b" ")
            return result

        with patch.object(fixed_boot_fixture, "_package", side_effect=drift):
            try:
                fixed_boot_fixture.prepare(root, "out/drift")
            except package_artifacts.PackageError as error:
                ensure("source changed" in str(error), str(error))
            else:
                raise AssertionError("changed fixture source published a construction verdict")
        ensure(not (root / "out/drift/fixture.json").exists(), "source drift published a fixture record")


def cases() -> list[Case]:
    return [Case("two translated layouts reuse one actual construction per package", _construction_once),
            Case("translated observer recipes replay and refuse a missing peer", _translated_observation_and_missing_peer),
            Case("fixture output and changed source refuse without a success record", _fresh_output_and_source_drift)]
