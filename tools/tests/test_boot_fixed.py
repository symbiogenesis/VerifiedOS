# SPDX-License-Identifier: Apache-2.0
"""Fixed-package images reach the existing observer without producer reruns."""

import copy
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests import test_boot
from tests.harness import TOOLS, Case, ensure
from tests.test_package_artifacts import fixture_request
from vos import asm, boot, fixed_boot, fixed_composition, package_artifacts
from vos.cli import boot as cli

TOHOST = 0x80000100
PROGRAM = '''
import json, sys, time
plan = json.load(open(sys.argv[1], encoding="utf-8"))
args = sys.argv[2:]
with open(args[args.index("--terminal-log") + 1], "wb") as output:
    output.write(plan["console"].encode())
time.sleep(plan.get("sleep", 0))
for line in plan["lines"]:
    print(line, flush=True)
sys.exit(plan.get("exit", 0))
'''


def fixture(root: Path, *, peer: bool = False) -> str:
    request, _ = fixture_request(root, "observer")
    source = (TOOLS / "boot/fixed-observer.s").read_bytes()
    sections, _, _ = asm.Assembler(source.decode(), "fixed-observer", text_base=0x80000000,
                                   data_base=TOHOST).assemble()
    for key, blob in (("source_closure", source),):
        reference = {"sha256": package_artifacts.digest(blob), "bytes": len(blob)}
        request["manifest"][key] = reference
    replacements = [source, bytes(sections[0].data), bytes(sections[1].data)]
    for index, blob in zip((0, 2, 3), replacements, strict=True):
        reference = {"sha256": package_artifacts.digest(blob), "bytes": len(blob)}
        path = f"inputs/{reference['sha256']}.bin"
        (root / path).write_bytes(blob)
        request["objects"][index] = {**reference, "path": path}
        if index:
            request["manifest"]["regions"][index - 2]["object"] = reference
    request["manifest"]["exports"].append({"name": "tohost", "offset": 256})
    (root / "observer.json").write_bytes(package_artifacts.canonical(request))
    artifact = package_artifacts.read_request(root, "observer.json")
    package_artifacts.store(root / "out/store", artifact)
    composition: dict[str, Any] = {
        "schema_version": 1, "context": artifact.document()["context"],
        "packages": [{"artifact": artifact.identity, "base": 0x80000000}],
        "memory": [{"base": 0x80000000, "size": 65536, "memory_class": 0,
                    "writable": True, "executable": True}], "entry": artifact.identity}
    if peer:
        second, _ = fixture_request(root, "peer")
        (root / "peer.json").write_bytes(package_artifacts.canonical(second))
        second_artifact = package_artifacts.read_request(root, "peer.json")
        package_artifacts.store(root / "out/store", second_artifact)
        composition["packages"].append({"artifact": second_artifact.identity, "base": 0x80001000})
    (root / "composition.json").write_bytes(package_artifacts.canonical(composition))
    fixed_composition.compose(root, "composition.json", "out/store", "out/image.elf")
    shutil.copyfile(TOOLS.parent / "model/config/verifiedos.json", root / "configuration.json")
    raw = {"schema_version": 1, "name": "observer", "composition": "composition.json",
           "store": "out/store", "image": "out/image.elf", "configuration": "configuration.json",
           "inst_limit": 100, "tohost": hex(TOHOST), "expected": None}
    (root / "boot.json").write_bytes(package_artifacts.canonical(raw))
    (root / "simulator.py").write_text(PROGRAM, encoding="utf-8")
    return "boot.json"


def _lines(*, peer: bool = False) -> list[str]:
    result = ["I 0 0000000080000000 00000013",
              f"W {TOHOST:X} 8 0 0101000000000046"]
    if peer:
        result += ["I 1 0000000080001000 00000013"]
    return [*result, f"W {TOHOST:X} 8 0 0000000000000001", "SUCCESS"]


def _run(root: Path, *, refresh: bool = False, plan: dict[str, Any] | None = None,
         timeout: float = 10) -> dict[str, Any]:
    (root / "plan.json").write_text(json.dumps(plan or {"console": "F", "lines": _lines()}), encoding="utf-8")
    original = boot.subprocess.Popen

    def process(argv: list[str], *, stdout: int, stderr: int, text: bool,
                encoding: str, errors: str, cwd: Path | None) -> subprocess.Popen[str]:
        return original([sys.executable, argv[0], str(root / "plan.json"), *argv[1:]],
                        stdout=stdout, stderr=stderr, text=text, encoding=encoding, errors=errors, cwd=cwd)

    with patch.object(boot.subprocess, "Popen", side_effect=process):
        return fixed_boot.run(root, fixed_boot.load_recipe(root, "boot.json"), root / "out/observe",
                              root / "simulator.py", timeout=timeout, refresh=refresh, keep_trace=True)


def _capture_and_replay() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-boot-fixed-") as directory:
        root = Path(directory)
        fixture(root)
        original_image = (root / "out/image.elf").read_bytes()
        with patch.object(asm.Assembler, "assemble", side_effect=AssertionError("producer reran")):
            captured = _run(root, refresh=True)
            replay = _run(root)
        ensure(captured["findings"] == replay["findings"] == [] and captured["refreshed"] is True,
               f"scripted observation should capture and replay: {captured}, {replay}")
        ensure(captured["image_sha256"] == replay["image_sha256"]
               and (root / "out/image.elf").read_bytes() == original_image,
               "fixed image and package producer remain unchanged")
        ensure(replay["production_admission"] is False and replay["final_target_acceptance"] is False
               and replay["roster_identity"] is None, "scripted processes supply no target acceptance")
        ensure(json.loads((root / "out/observe/run.json").read_bytes()) == replay,
               "saved result binds exact observer inputs and outputs")


def _process_and_digest_findings() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-boot-fixed-refusals-") as directory:
        root = Path(directory)
        fixture(root)
        _run(root, refresh=True)
        before = (root / "boot.json").read_bytes()
        for plan, needle, timeout in (
                ({"console": "F", "lines": _lines(), "exit": 3}, "process exited 3", 10),
                ({"console": "", "lines": [], "sleep": 10}, "timeout", 0.2),
                ({"console": "X", "lines": _lines()}, "console file", 10),
                ({"console": "F", "lines": _lines()[1:]}, "never entered", 10)):
            result = _run(root, refresh=True, plan=plan, timeout=timeout)
            ensure(any(needle in item for item in result["findings"]), f"missing {needle}: {result}")
            ensure((root / "boot.json").read_bytes() == before, "failed capture changed expected values")
        changed = _lines()
        changed.insert(1, "X 5 0 0000000000000007")
        result = _run(root, plan={"console": "F", "lines": changed})
        ensure(any("commit trace" in item for item in result["findings"]), "trace mismatch was ignored")


def _identity_and_order_refusals() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-boot-fixed-identities-") as directory:
        root = Path(directory)
        fixture(root, peer=True)
        positive = _run(root, refresh=True, plan={"console": "F", "lines": _lines(peer=True)})
        ensure(positive["findings"] == [], f"two-package observation refused: {positive}")
        reordered = _lines(peer=True)
        reordered[0], reordered[2] = reordered[2], reordered[0]
        result = _run(root, plan={"console": "F", "lines": reordered})
        ensure(any("composed order" in item for item in result["findings"]), "first-entry order was ignored")
        image = root / "out/image.elf"
        original = image.read_bytes()
        for replacement in (b"broken image", original[:24] + struct.pack("<Q", 0x80001000) + original[32:]):
            image.write_bytes(replacement)
            with patch.object(boot, "boot_image", side_effect=AssertionError("stale image launched")):
                try:
                    _run(root)
                except package_artifacts.PackageError:
                    pass
                else:
                    raise AssertionError("changed fixed image was accepted")
        image.write_bytes(original)


def _strict_recipe_and_output_refusals() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-boot-fixed-inputs-") as directory:
        root = Path(directory)
        fixture(root)
        raw = json.loads((root / "boot.json").read_bytes())
        for field, value in (("schema_version", True), ("inst_limit", 1.0),
                             ("configuration", "../outside.json"), ("unknown", 1)):
            changed = copy.deepcopy(raw)
            changed[field] = value
            (root / "boot.json").write_bytes(package_artifacts.canonical(changed))
            try:
                fixed_boot.load_recipe(root, "boot.json")
            except (boot.RecipeError, package_artifacts.PackageError):
                pass
            else:
                raise AssertionError(f"malformed recipe accepted {field}")
        (root / "boot.json").write_bytes(package_artifacts.canonical(raw))
        shutil.copyfile(root / "out/image.elf", root / "out/console.log")
        raw["image"] = "out/console.log"
        (root / "boot.json").write_bytes(package_artifacts.canonical(raw))
        image = (root / "out/console.log").read_bytes()
        with patch.object(boot, "boot_image", side_effect=AssertionError("input alias launched")):
            try:
                fixed_boot.run(root, fixed_boot.load_recipe(root, "boot.json"), root / "out",
                               root / "simulator.py", timeout=10)
            except boot.RefusalError as error:
                ensure("aliases" in str(error), str(error))
            else:
                raise AssertionError("observer output could overwrite image input")
        ensure((root / "out/console.log").read_bytes() == image, "alias refusal overwrote image")
        output = io.StringIO()
        with patch.object(cli.corpus, "find_root", return_value=root), redirect_stdout(output):
            code = cli.main(["run-fixed", "boot.json", "--out", str(root / "out"),
                             "--simulator", str(root / "simulator.py")])
        ensure(code == 1 and "aliases" in output.getvalue(), output.getvalue())


def _stored_input_aliases_and_configuration() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-boot-fixed-store-alias-") as directory:
        root = Path(directory)
        fixture(root)
        paths = [*sorted((root / "out/store/manifests").glob("*.json")),
                 *sorted((root / "out/store/objects").glob("*.bin"))]
        for source in paths:
            for name in ("console.log", "trace.log", "events.log", "run.json"):
                destination = root / "out/observe" / name
                destination.parent.mkdir(exist_ok=True)
                os.link(source, destination)
                before = source.read_bytes()
                try:
                    with patch.object(boot, "boot_image", side_effect=AssertionError("stored alias launched")):
                        _run(root)
                except boot.RefusalError as error:
                    ensure("aliases" in str(error), str(error))
                else:
                    raise AssertionError("observer could overwrite a retained object through a hardlink")
                ensure(source.read_bytes() == before, "stored-input alias refusal changed retained bytes")
                destination.unlink()
        config = root / "configuration.json"
        before = config.read_bytes()
        config.write_bytes(before.replace(b'"mem_type": "MainMemory",',
                                         b'"mem_type": "Device", "mem_type": "MainMemory",', 1))
        with patch.object(boot, "boot_image", side_effect=AssertionError("ambiguous config launched")):
            try:
                _run(root)
            except boot.RecipeError as error:
                ensure("duplicate" in str(error), str(error))
            else:
                raise AssertionError("duplicate model configuration fields accepted")


def _changed_inputs_refuse_refresh() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-boot-fixed-drift-") as directory:
        root = Path(directory)
        fixture(root)
        _run(root, refresh=True)
        checked = (root / "boot.json").read_bytes()
        original = boot.boot_image
        targets = [root / "boot.json", root / "composition.json", root / "configuration.json",
                   root / "out/image.elf", next((root / "out/store/objects").glob("*.bin"))]
        for target in targets:
            before = target.read_bytes()

            def changed(argv: list[str], console_path: Path, entries: dict[int, str],
                        tohost: int, timeout: float, trace_path: Path | None = None, *,
                        cwd: Path | None = None, changed_path: Path = target,
                        changed_bytes: bytes = before) -> boot.Observation:
                observation = original(argv, console_path, entries, tohost, timeout, trace_path, cwd=cwd)
                changed_path.write_bytes(changed_bytes + b" ")
                return observation

            with patch.object(boot, "boot_image", side_effect=changed):
                result = _run(root, refresh=True)
            ensure(any("binding" in item for item in result["findings"]),
                   f"changed {target.name} escaped the final binding: {result}")
            ensure(result["refreshed"] is False, "changed input refreshed expected values")
            target.write_bytes(before)
            ensure((root / "boot.json").read_bytes() == checked, "failed refresh changed the reviewed recipe")


def _shared_expectation_reader() -> None:
    test_boot._recipe_refusals()
    test_boot._against_expected()


def cases() -> list[Case]:
    return [Case("scripted fixed-image capture and replay never invoke producers", _capture_and_replay),
            Case("process and digest findings preserve reviewed expectations", _process_and_digest_findings),
            Case("fixed image identity and package first-entry order refuse", _identity_and_order_refusals),
            Case("closed recipe and output aliases refuse before launch", _strict_recipe_and_output_refusals),
            Case("retained input hardlinks and ambiguous configuration refuse", _stored_input_aliases_and_configuration),
            Case("final input drift prevents expected-value refresh", _changed_inputs_refuse_refresh),
            Case("shared expectation reading retains legacy recipe and digest controls", _shared_expectation_reader)]
