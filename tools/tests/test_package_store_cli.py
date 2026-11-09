# SPDX-License-Identifier: Apache-2.0
"""The public producer-import options reach actual ELF checks before publication."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from tests.test_fixed_composition import _run, producer_fixture
from vos import asm, package_artifacts


def _explicit_producer_import() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-package-import-cli-") as directory:
        root = Path(directory)
        source, producer, _ = producer_fixture(root)
        original = producer.read_bytes()
        with patch.object(asm.Assembler, "assemble", side_effect=AssertionError("producer reran")):
            code, output = _run(root, ["package-store", source, "--store", "out/imported",
                                      "--producer-image", "out/producer.elf", "--producer-base", "0x80000000"])
            ensure(code == 0, output)
            result = json.loads(output)
            artifact = package_artifacts.load(root / "out/imported", result["artifact"])
            ensure(result["producer_image"] == {"path": "out/producer.elf", "base": 0x80000000,
                                                "sha256": package_artifacts.digest(original)}
                   and artifact.package_id == "produced" and result["production_admission"] is False,
                   "CLI must bind the actual producer bytes without claiming admission")
            preserved = root / "out/refused/useful"
            preserved.parent.mkdir()
            preserved.write_bytes(b"retained evidence")
            for options in (["--producer-image", "out/producer.elf"],
                            ["--producer-base", "0x80000000"],
                            ["--producer-image", "out/producer.elf", "--producer-base", "0x80001000"]):
                code, output = _run(root, ["package-store", source, "--store", "out/refused", *options])
                ensure(code == 1 and "FAIL composer:" in output,
                       f"invalid producer options reached publication: {options}: {output}")
                ensure(preserved.read_bytes() == b"retained evidence"
                       and not (preserved.parent / "manifests").exists(),
                       "refused producer import published a root or damaged useful prior output")
        ensure(producer.read_bytes() == original, "CLI import changed its producer input")


def cases() -> list[Case]:
    return [Case("public producer flags bind real ELF bytes and refuse incomplete or wrong bases",
                 _explicit_producer_import)]
