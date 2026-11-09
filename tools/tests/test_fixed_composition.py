# SPDX-License-Identifier: Apache-2.0
"""The public fixed-package commands compose actual stored bytes without producers."""

import copy
import json
import struct
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.harness import Case, ensure
from tests.test_package_artifacts import fixture_artifact
from vos import asm, fixed_composition, image, package_artifacts
from vos.cli import composer


def fixture_recipe(root: Path) -> str:
    artifact = fixture_artifact(root, "cli-example")
    package_artifacts.store(root / "out/native-packages", artifact)
    raw = {"schema_version": 1, "context": artifact.document()["context"],
           "packages": [{"artifact": artifact.identity, "base": 0x80000000}],
           "memory": [{"base": 0x80000000, "size": 65536, "memory_class": 0,
                       "writable": True, "executable": True}], "entry": artifact.identity}
    name = "fixed-recipe.json"
    (root / name).write_bytes(package_artifacts.canonical(raw))
    return name


def fixture_store(root: Path) -> str:
    fixture_artifact(root, "cli-stored")
    return "cli-stored.json"


def _run(root: Path, args: list[str]) -> tuple[int, str]:
    out = StringIO()
    with patch.object(composer.corpus, "find_root", return_value=root), redirect_stdout(out):
        code = composer.main(args)
    return code, out.getvalue()


def _commands_reuse_the_actual_artifact() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-fixed-cli-") as directory:
        root = Path(directory)
        source = fixture_store(root)
        with patch.object(asm.Assembler, "assemble", side_effect=AssertionError("producer reran")):
            code, out = _run(root, ["package-store", source])
            ensure(code == 0, out)
            stored = json.loads(out)
            artifact = package_artifacts.load(root / "out/native-packages", stored["artifact"])
            raw: dict[str, Any] = {"schema_version": 1, "context": artifact.document()["context"],
                   "packages": [{"artifact": artifact.identity, "base": 0x80000000}],
                   "memory": [{"base": 0x80000000, "size": 65536, "memory_class": 0,
                               "writable": True, "executable": True}], "entry": artifact.identity}
            retained = {path.relative_to(root).as_posix(): path.read_bytes()
                        for path in (root / "out/native-packages").rglob("*") if path.is_file()}
            for index, base in enumerate((0x80000000, 0x80001000)):
                raw["packages"][0]["base"] = base
                (root / "recipe.json").write_bytes(package_artifacts.canonical(raw))
                destination = f"out/generation-{index}.elf"
                code, out = _run(root, ["compose-fixed", "recipe.json", "--output", destination])
                ensure(code == 0, out)
                report = json.loads(out)
                ensure(report["packages"][0]["artifact"] == artifact.identity
                       and report["packages"][0]["base"] == base
                       and report["production_admission"] is False,
                       "public composition preserves artifact identity and its honest producer scope")
                package_artifacts.verify_image((root / destination).read_bytes(),
                                               [package_artifacts.place(artifact, base)])
            ensure(retained == {path.relative_to(root).as_posix(): path.read_bytes()
                                for path in (root / "out/native-packages").rglob("*") if path.is_file()},
                   "successor layout does not rewrite unchanged package objects or proofs")


def _replace_only_one_package() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-fixed-update-") as directory:
        root = Path(directory)
        source = fixture_recipe(root)
        raw = json.loads((root / source).read_bytes())
        original = raw["packages"][0]["artifact"]
        old = fixture_artifact(root, "changed", marker=9)
        new = fixture_artifact(root, "changed", marker=10)
        for artifact in (old, new):
            package_artifacts.store(root / "out/native-packages", artifact)
        with patch.object(asm.Assembler, "assemble", side_effect=AssertionError("producer reran")):
            for index, artifact in enumerate((old, new)):
                raw["packages"] = [{"artifact": original, "base": 0x80000000},
                                   {"artifact": artifact.identity, "base": 0x80001000}]
                (root / source).write_bytes(package_artifacts.canonical(raw))
                result = fixed_composition.compose(root, source, "out/native-packages", f"out/update-{index}.elf")
                members = result["packages"]
                ensure(isinstance(members, list) and members[0]["artifact"] == original
                       and members[1]["artifact"] == artifact.identity,
                       "only the changed package identity moves between native generations")


def _refusals_preserve_output() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-fixed-cli-refusals-") as directory:
        root = Path(directory)
        source = fixture_recipe(root)
        original = json.loads((root / source).read_bytes())
        destination = root / "out/preserved.elf"
        destination.write_bytes(b"old generation")
        variants: list[dict[str, Any]] = []
        bad = copy.deepcopy(original)
        bad["packages"][0]["base"] = True
        variants.append(bad)
        bad = copy.deepcopy(original)
        bad["memory"][0]["memory_class"] = 1
        variants.append(bad)
        bad = copy.deepcopy(original)
        bad["context"]["model"] = "2" * 64
        variants.append(bad)
        bad = copy.deepcopy(original)
        bad["entry"] = "0" * 64
        variants.append(bad)
        bad = copy.deepcopy(original)
        bad["packages"].append(bad["packages"][0])
        variants.append(bad)
        bad = copy.deepcopy(original)
        bad["accepted"] = True
        variants.append(bad)
        for raw in variants:
            (root / source).write_bytes(package_artifacts.canonical(raw))
            code, out = _run(root, ["compose-fixed", source, "--output", "out/preserved.elf"])
            ensure(code == 1 and out.startswith("FAIL composer:"), out)
            ensure(destination.read_bytes() == b"old generation", "refused composition replaced a generation")
        (root / source).write_bytes(package_artifacts.canonical(original))
        for output in (source, "out/native-packages/objects/substitute.bin", "../outside.elf"):
            code, out = _run(root, ["compose-fixed", source, "--output", output])
            ensure(code == 1 and out.startswith("FAIL composer:"), out)
        (root / source).write_bytes(b" " * (package_artifacts.MANIFEST_LIMIT + 1))
        code, out = _run(root, ["compose-fixed", source, "--output", "out/preserved.elf"])
        ensure(code == 1 and "byte limit" in out and destination.read_bytes() == b"old generation", out)


def _selected_entry_substitution_preserves_output() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-fixed-entry-") as directory:
        root = Path(directory)
        source = fixture_recipe(root)
        raw = json.loads((root / source).read_bytes())
        sibling = fixture_artifact(root, "sibling")
        package_artifacts.store(root / "out/native-packages", sibling)
        raw["packages"].append({"artifact": sibling.identity, "base": 0x80001000})
        original = image.write_elf
        destination = root / "out/generation.elf"
        for selected in (raw["packages"][0]["artifact"], sibling.identity):
            raw["entry"] = selected
            (root / source).write_bytes(package_artifacts.canonical(raw))
            args = ["compose-fixed", source, "--output", "out/generation.elf"]
            code, report = _run(root, args)
            ensure(code == 0, report)
            selected_base = next(item["base"] for item in raw["packages"] if item["artifact"] == selected)
            ensure(struct.unpack_from("<Q", destination.read_bytes(), 24)[0] == selected_base,
                   "composition starts at the recipe-selected member")
            previous = destination.read_bytes()
            alternate = next(item["base"] for item in raw["packages"] if item["artifact"] != selected)

            def substituted(path: Path, sections: list[image.Section], symbols: dict[str, tuple[str, int]],
                            entry: int, *, alternate_entry: int = alternate) -> None:
                original(path, sections, symbols, entry)
                blob = bytearray(path.read_bytes())
                struct.pack_into("<Q", blob, 24, alternate_entry)
                path.write_bytes(blob)

            with patch.object(image, "write_elf", side_effect=substituted):
                code, report = _run(root, args)
            ensure(code == 1 and "selected package entry" in report, report)
            ensure(destination.read_bytes() == previous,
                   "a valid sibling entry substitution preserves the prior generation")


def cases() -> list[Case]:
    return [Case("public commands reuse exact stored native bytes at two layouts", _commands_reuse_the_actual_artifact),
            Case("one changed package leaves its unchanged neighbor intact", _replace_only_one_package),
            Case("bad context placement and output aliases preserve the old image", _refusals_preserve_output),
            Case("another valid package entry refuses before replacing the generation", _selected_entry_substitution_preserves_output)]
