# SPDX-License-Identifier: Apache-2.0
"""A focused simulator dependency for Q39 replay, separate from full model acceptance."""

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import cast

from vos import config, env, receipts
from vos.jsonc import Json

SCHEMA = "verifiedos-focused-simulator-build/1"
PROFILE = "q39-compiler-replay"
TARGET = "sail_riscv_sim"
ARTIFACT = "c_emulator/sail_riscv_sim"
_SHA = re.compile(r"[0-9a-f]{64}")


def _mapping(raw: object) -> dict[str, Json]:
    if not isinstance(raw, dict):
        raise TypeError("simulator receipt requires an identity object")
    return cast("dict[str, Json]", raw)


def _hash(raw: object) -> bool:
    return isinstance(raw, str) and _SHA.fullmatch(raw) is not None


def _tools(e: env.Environment) -> dict[str, Json]:
    cpp = next((arg.split("=", 1)[1] for arg in e.compilers
                if arg.startswith("-DCMAKE_CXX_COMPILER=")), "c++")
    result: dict[str, Json] = {}
    for role, name in (("sail", "sail"), ("cmake", "cmake"), ("cxx", cpp)):
        found = shutil.which(name)
        if found is None:
            raise FileNotFoundError(f"required simulator producer is missing: {name}")
        ran = subprocess.run([found, "--version"], capture_output=True, text=True,
                             check=True, timeout=30)
        reported = (ran.stdout + ran.stderr).strip()
        if not reported:
            raise ValueError(f"simulator producer reports no version: {name}")
        result[role] = {"executable": str(Path(found).absolute()),
                        "sha256": receipts.digest(Path(found)), "reported_version": reported}
    return result


def _identity(e: env.Environment) -> dict[str, Json]:
    if e.model.resolve() != (e.root / "model").resolve():
        raise ValueError("focused simulator requires this checkout's current model")
    return {"model_inputs": cast("dict[str, Json]", receipts.inputs(e.root, "model")),
            "profile_sha256": receipts.digest(e.profile), "tools": _tools(e),
            "compiler_options": cast("list[Json]", e.compilers),
            "cache_options": cast("list[Json]", e.ccache)}


def read(root: Path, simulator: Path, path: Path) -> dict[str, Json]:
    """Admit only this narrow profile, binding stages, identities and current bytes."""
    record = _mapping(json.loads(path.read_text(encoding="utf-8")))
    if (record.get("schema") != SCHEMA or record.get("profile") != PROFILE
            or record.get("passed") is not True or record.get("inputs_unchanged") is not True
            or type(record.get("exit_code")) is not int or record["exit_code"] != 0
            or record.get("bundled_model_tests") != "not-run"
            or record.get("full_model_acceptance") != "pending"
            or type(record.get("profile_validation_exit")) is not int
            or record["profile_validation_exit"] != 0):
        raise ValueError("focused simulator receipt does not establish successful dependency stages")
    identity = _mapping(record.get("identity"))
    if (identity.get("model_inputs") != receipts.inputs(root, "model")
            or identity.get("profile_sha256") != receipts.digest(root / "model/config/verifiedos.json")):
        raise ValueError("focused simulator receipt is stale: model population or profile changed")
    tools = _mapping(identity.get("tools"))
    if set(tools) != {"sail", "cmake", "cxx"}:
        raise ValueError("focused simulator receipt is missing actual producer identities")
    for raw in tools.values():
        tool = _mapping(raw)
        executable, reported = tool.get("executable"), tool.get("reported_version")
        if (not isinstance(executable, str) or not Path(executable).is_absolute()
                or not _hash(tool.get("sha256")) or not isinstance(reported, str)
                or not reported.strip()):
            raise ValueError("focused simulator producer identity is malformed")
    stages = _mapping(record.get("stages"))
    if set(stages) != {"configure", "target-build"}:
        raise ValueError("focused simulator stages must be configure and explicit target build")
    for name, raw in stages.items():
        stage = _mapping(raw)
        argv = stage.get("argv")
        if (type(stage.get("exit")) is not int or stage["exit"] != 0
                or not isinstance(argv, list) or not argv
                or not all(isinstance(arg, str) and arg for arg in argv)
                or argv[0] != _mapping(tools["cmake"])["executable"]
                or not _hash(stage.get("log_sha256"))
                or receipts.digest(path.parent / "logs" / (name + ".log")) != stage["log_sha256"]):
            raise ValueError(f"focused simulator {name} stage or log is invalid")
        if name == "target-build":
            if (argv[-2:] != ["--target", TARGET] or argv.count("--target") != 1
                    or argv.count("--build") != 1):
                raise ValueError("focused simulator receipt did not build the explicit target")
        elif "-S" not in argv or "-B" not in argv or not any(
                arg == "-DSAIL_BIN=" + str(_mapping(tools["sail"])["executable"])
                for arg in argv):
            raise ValueError("focused simulator configure does not bind its Sail producer")
    if _mapping(record.get("artifacts")).get(ARTIFACT) != receipts.digest(simulator):
        raise ValueError("focused simulator differs from the recorded build artifact")
    return record


def build(e: env.Environment, out: Path) -> int:
    """Configure and build one explicit target in a fresh, exclusively locked lane."""
    from vos.cli import model  # noqa: PLC0415
    if not out.is_absolute() or not out.resolve().is_relative_to(e.lane_root.resolve()):
        raise ValueError("focused simulator output must be absolute in this checkout's native lane")
    out = out.resolve()
    if out == e.lane_root.resolve():
        raise ValueError("focused simulator needs its own output directory")
    out.mkdir(parents=True, exist_ok=False)
    logs = out / "logs"
    logs.mkdir()
    directory = out / "build"
    stages: dict[str, Json] = {}
    before = _identity(e)
    cmake = str(_mapping(_mapping(before["tools"])["cmake"])["executable"])
    commands = {"configure": [cmake, *model.configure_command(e, directory)[1:]],
                "target-build": [cmake, "--build", str(directory), "-j", str(e.jobs),
                                 "--target", TARGET]}
    passed = True
    lock = env.build_lock(directory)
    try:
        for name, argv in commands.items():
            if not passed:
                break
            began = time.monotonic()
            print(f"START focused simulator {name}", flush=True)
            log = logs / (name + ".log")
            with log.open("w", encoding="utf-8") as stream:
                ran = subprocess.run(argv, cwd=out, stdout=stream, stderr=subprocess.STDOUT,
                                     env={**os.environ, **env.git_env(e.root)}, check=False)
            stages[name] = {"argv": cast("list[Json]", argv), "exit": ran.returncode,
                            "seconds": time.monotonic() - began, "log_sha256": receipts.digest(log)}
            passed = ran.returncode == 0
            print(f"END focused simulator {name}: {ran.returncode}", flush=True)
        validation, messages = (config.validate(directory / model.SCHEMA, e.profile)
                                if passed else (1, ["build stage failed"]))
        (logs / "profile-validation.log").write_text("\n".join(messages) + "\n", encoding="utf-8")
        after = _identity(e)
        unchanged = before == after
        simulator = directory / ARTIFACT
        artifacts = {ARTIFACT: receipts.digest(simulator)} if simulator.is_file() else {}
        passed = passed and validation == 0 and unchanged and bool(artifacts)
        record: dict[str, Json] = {"schema": SCHEMA, "profile": PROFILE,
            "passed": passed, "exit_code": 0 if passed else 1, "inputs_unchanged": unchanged,
            "identity": before, "stages": stages, "profile_validation_exit": validation,
            "artifacts": artifacts, "bundled_model_tests": "not-run",
            "full_model_acceptance": "pending"}
        path = out / "simulator-build.json"
        if passed:
            # Validate the exported shape and native log bindings before publishing it.
            with receipts.atomic_path(path) as pending:
                pending.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                                   encoding="utf-8")
                read(e.root, simulator, pending)
        else:
            receipts.write(path, record)
        print(json.dumps({"passed": passed, "receipt": str(path),
                          "bundled_model_tests": "not-run"}), flush=True)
        return 0 if passed else 1
    finally:
        if lock is not None:
            lock.close()
