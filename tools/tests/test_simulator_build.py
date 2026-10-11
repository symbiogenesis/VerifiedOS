# SPDX-License-Identifier: Apache-2.0
"""The focused replay dependency cannot masquerade as complete model acceptance."""

import copy
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import env, receipts
from vos import simulator_build as dependency


def _inputs(root: Path, *_: str) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): receipts.digest(path)
            for path in sorted((root / "model").rglob("*")) if path.is_file()}


def fixture(root: Path) -> tuple[Path, Path, dict[str, Any]]:
    model = root / "model"
    (model / "config").mkdir(parents=True)
    (model / "config/verifiedos.json").write_text("{}", encoding="utf-8")
    (model / "source.sail").write_text("original", encoding="utf-8")
    out = root / "native"
    (out / "logs").mkdir(parents=True)
    simulator = out / "sail_riscv_sim"
    simulator.write_bytes(b"simulator")
    tools = {}
    for role in ("sail", "cmake", "cxx"):
        (root / role).write_bytes(role.encode())
        tools[role] = {"executable": str(root / role), "sha256": receipts.digest(root / role),
                       "reported_version": role + " version"}
    build = out / "build"
    build.mkdir()
    cache = (f"SAIL_BIN:FILEPATH={root / 'sail'}\n"
             f"CMAKE_CXX_COMPILER:FILEPATH={root / 'cxx'}\n"
             f"CMAKE_HOME_DIRECTORY:INTERNAL={model}\n"
             f"CMAKE_CACHEFILE_DIR:INTERNAL={build}\n")
    (build / dependency.CACHE).write_text(cache, encoding="utf-8")
    (build / dependency.CONFIG_SCHEMA).write_text("{}", encoding="utf-8")
    validation_log = out / "logs/profile-validation.log"
    validation_log.write_text("valid", encoding="utf-8")
    commands = {"configure": [str(root / "cmake"), "-S", str(model), "-B", str(build),
                               "-DSAIL_BIN=" + str(root / "sail")],
                "target-build": [str(root / "cmake"), "--build", str(build),
                                  "--target", dependency.TARGET]}
    stages = {}
    for name, argv in commands.items():
        log = out / "logs" / (name + ".log")
        log.write_text(name, encoding="utf-8")
        stages[name] = {"argv": argv, "exit": 0, "log_sha256": receipts.digest(log)}
    record = {"schema": dependency.SCHEMA, "profile": dependency.PROFILE, "passed": True,
              "exit_code": 0, "inputs_unchanged": True, "profile_validation_exit": 0,
              "identity": {"model_inputs": _inputs(root), "source_root": str(model),
                           "profile_sha256": receipts.digest(model / "config/verifiedos.json"),
                           "tools": tools}, "stages": stages,
              "build_root": str(build),
              "configured_producers": {role: {"cache_entry": entry, "executable": str(root / role),
                                               "sha256": tools[role]["sha256"]}
                  for role, entry in (("sail", "SAIL_BIN"), ("cxx", "CMAKE_CXX_COMPILER"))},
              "artifacts": {dependency.ARTIFACT: receipts.digest(simulator),
                            dependency.CACHE: receipts.digest(build / dependency.CACHE),
                            dependency.CONFIG_SCHEMA: receipts.digest(build / dependency.CONFIG_SCHEMA)},
              "configuration_evidence": {"cache_sha256": receipts.digest(build / dependency.CACHE),
                  "schema_sha256": receipts.digest(build / dependency.CONFIG_SCHEMA),
                  "profile_sha256": receipts.digest(model / "config/verifiedos.json"),
                  "validation_log_sha256": receipts.digest(validation_log)},
              "bundled_model_tests": "not-run", "full_model_acceptance": "pending"}
    return simulator, out / "simulator-build.json", record


def consumer_refusals() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-focused-simulator-") as name:
        root = Path(name)
        simulator, path, original = fixture(root)
        with patch.object(receipts, "inputs", side_effect=_inputs):
            receipts.write(path, original)
            ensure(dependency.read(root, simulator, path)["passed"] is True,
                   "honest focused dependency refused")
            mutants = []
            for key, value in (("schema", 1), ("profile", "general-target"), ("passed", False),
                               ("inputs_unchanged", False), ("exit_code", 1),
                               ("bundled_model_tests", "passed"),
                               ("full_model_acceptance", "passed"), ("profile_validation_exit", 1)):
                record = copy.deepcopy(original)
                record[key] = value
                mutants.append(record)
            for role in ("sail", "cmake", "cxx"):
                for field in (None, "sha256", "reported_version", "executable"):
                    record = copy.deepcopy(original)
                    if field is None:
                        del record["identity"]["tools"][role]
                    else:
                        record["identity"]["tools"][role][field] = ""
                    mutants.append(record)
            for stage in ("configure", "target-build"):
                record = copy.deepcopy(original)
                record["stages"][stage]["exit"] = 2
                mutants.append(record)
            record = copy.deepcopy(original)
            record["stages"]["target-build"]["argv"][-1] = "all"
            mutants.append(record)
            record = copy.deepcopy(original)
            record["identity"]["model_inputs"].pop("model/source.sail")
            mutants.append(record)
            for stage, flag in (("configure", "-S"), ("configure", "-B"),
                                ("target-build", "--build")):
                record = copy.deepcopy(original)
                argv = record["stages"][stage]["argv"]
                argv[argv.index(flag) + 1] += "-other"
                mutants.append(record)
            record = copy.deepcopy(original)
            record["configured_producers"]["cxx"]["sha256"] = "2" * 64
            mutants.append(record)
            record = copy.deepcopy(original)
            record["configuration_evidence"]["schema_sha256"] = "2" * 64
            mutants.append(record)
            for record in mutants:
                receipts.write(path, record)
                try:
                    dependency.read(root, simulator, path)
                except (ValueError, TypeError):
                    continue
                raise AssertionError("invalid focused simulator receipt admitted")
            receipts.write(path, original)
            for changed in (simulator, root / "model/source.sail",
                            path.parent / "logs/configure.log", path.parent / "build" / dependency.CACHE,
                            path.parent / "build" / dependency.CONFIG_SCHEMA):
                before = changed.read_bytes()
                changed.write_bytes(before + b"changed")
                try:
                    dependency.read(root, simulator, path)
                except (ValueError, TypeError):
                    pass
                else:
                    raise AssertionError("changed simulator, model or stage log admitted")
                changed.write_bytes(before)


def producer_checks() -> None:
    for defect in ("none", "source-moved", "tool-moved", "target-failed"):
        with tempfile.TemporaryDirectory(prefix="vos-focused-producer-") as name:
            root = Path(name)
            _, _, original = fixture(root)
            e = env.Environment(root, root / "model", root, root, "", 2, 4096, 2, 2)
            out = e.lane_root / "focused"
            tools = original["identity"]["tools"]
            altered_tools = copy.deepcopy(tools)
            altered_tools["cxx"]["sha256"] = "2" * 64
            tool_reads = [tools, altered_tools if defect == "tool-moved" else tools]
            configured = [str(root / "cmake"), "-S", str(e.model), "-B", str(out / "build"),
                          "-DSAIL_BIN=" + str(root / "sail")]
            calls = []

            def stage(argv: list[str], *, _calls: list[list[str]] = calls,
                      _out: Path = out, _defect: str = defect, _model: Path = e.model,
                      _tools: dict[str, Any] = tools,
                      **_: object) -> subprocess.CompletedProcess[str]:
                _calls.append(argv)
                directory = _out / "build"
                directory.mkdir(parents=True, exist_ok=True)
                if "-S" in argv:
                    (directory / dependency.CACHE).write_text(
                        f"SAIL_BIN:FILEPATH={_tools['sail']['executable']}\n"
                        f"CMAKE_CXX_COMPILER:FILEPATH={_tools['cxx']['executable']}\n"
                        f"CMAKE_HOME_DIRECTORY:INTERNAL={_model}\n"
                        f"CMAKE_CACHEFILE_DIR:INTERNAL={directory}\n", encoding="utf-8")
                    (directory / dependency.CONFIG_SCHEMA).write_text("{}", encoding="utf-8")
                if "--build" in argv:
                    simulator = _out / "build" / dependency.ARTIFACT
                    simulator.parent.mkdir(parents=True, exist_ok=True)
                    simulator.write_bytes(b"produced simulator")
                    if _defect == "source-moved":
                        (_model / "source.sail").write_text("changed", encoding="utf-8")
                return subprocess.CompletedProcess(argv, 2 if _defect == "target-failed" and
                                                   "--build" in argv else 0)

            with (patch.object(receipts, "inputs", side_effect=_inputs),
                  patch.object(dependency, "_tools", side_effect=tool_reads),
                  patch("vos.cli.model.configure_command", return_value=configured),
                  patch.object(dependency.subprocess, "run", side_effect=stage),
                  patch.object(dependency.config, "validate", return_value=(0, ["valid"])),
                  patch.object(env, "build_lock", return_value=None) as locked):
                code = dependency.build(e, out)
            record = json.loads((out / "simulator-build.json").read_text(encoding="utf-8"))
            ensure((code == 0) is (defect == "none") and record["passed"] is (defect == "none"),
                   f"focused producer accepted {defect}")
            ensure(len(calls) == 2 and calls[1][-2:] == ["--target", dependency.TARGET]
                   and "ctest" not in str(calls) and locked.call_args.args == (out / "build",),
                   "focused producer broadened the build or did not hold its lane")


def cases() -> list[Case]:
    return [Case("focused dependency validates identities, source population and stages", consumer_refusals),
            Case("focused producer refuses source/tool movement and failed target", producer_checks)]
