# SPDX-License-Identifier: Apache-2.0
"""Model orchestration refuses unprepared inputs and stale native evidence."""

import argparse
import io
import json
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import env
from vos.cli import model, provision


def _environment(root: Path) -> env.Environment:
    return env.Environment(root, root / "model", root / "native", root / "logs",
                           "", 2, 4096, 2, 2, model_offline=True)


def _acquisition_precedes_configuration() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-model-preparation-") as directory:
        e = _environment(Path(directory))
        events: list[str] = []
        flags = ["-DVOS_MODEL_OFFLINE=ON", "-DFETCHCONTENT_FULLY_DISCONNECTED=ON"]

        def prepare(*_: object, **kw: object) -> list[str]:
            ensure(kw == {"offline": True}, "offline policy must reach acquisition")
            events.append("prepare")
            return flags

        def configure(_e: env.Environment, _tree: Path,
                      options: list[str] | None = None) -> list[str]:
            ensure(options == ["-DLOCAL=1", *flags], "verified inputs follow local build options")
            events.append("configure")
            return ["cmake", "fixture"]

        with (patch.object(model.model_dependencies, "prepare", side_effect=prepare),
              patch.object(model, "configure_command", side_effect=configure),
              patch.object(model.env, "git_env", return_value={}),
              patch.object(model.env, "stage", return_value=0) as stage):
            ensure(model._configure(e, e.build_dir, ["-DLOCAL=1"]) == 0,
                   "verified preparation permits configuration")
            ensure(events == ["prepare", "configure"] and stage.call_count == 1,
                   "configuration must follow verification exactly once")
        with (patch.object(model.model_dependencies, "prepare", side_effect=ValueError("corrupt archive")),
              patch.object(model.env, "stage") as stage, redirect_stderr(io.StringIO()) as output):
            ensure(model._configure(e, e.build_dir) == 1 and not stage.called,
                   "corrupt offline inputs must stop before CMake runs")
            ensure("corrupt archive" in output.getvalue(), "preparation refusal keeps its reason")


def _offline_selection() -> None:
    for value, wanted in (("0", False), ("1", True)):
        with patch.dict(env.os.environ, {"VOS_MODEL_OFFLINE": value}):
            ensure(env.model_offline() is wanted, "the declared offline policy must be respected")
    with patch.dict(env.os.environ, {"VOS_MODEL_OFFLINE": "false-ish"}):
        try:
            env.model_offline()
        except ValueError:
            pass
        else:
            raise AssertionError("malformed offline policy must refuse")
    with tempfile.TemporaryDirectory(prefix="vos-model-offline-") as directory:
        e = _environment(Path(directory))
        e.model_offline = False
        with (patch.object(model.env, "load", return_value=e),
              patch.object(model.env, "keepalive"),
              patch.object(model, "cmd_dependencies", return_value=0) as command):
            ensure(model.main(["dependencies", "--offline"]) == 0
                   and e.model_offline and command.call_count == 1,
                   "the command-line offline request must reach the selected command")


def _native_refusal_is_not_success() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-model-native-refusal-") as directory:
        e = _environment(Path(directory))
        e.build_dir.mkdir(parents=True)
        log = e.log("model-build")
        version = argparse.Namespace(stdout="Sail fixture")
        with (patch.object(model, "build_identity", return_value={"inputs": {}}),
              patch.object(model, "_configure", return_value=0),
              patch.object(model, "_native_start", return_value={}),
              patch.object(model, "_native_finish", side_effect=ValueError("header changed")),
              patch.object(model, "_early_decision", return_value=(False, "after")),
              patch.object(model, "_ctest_stage", return_value=0),
              patch.object(model.env, "stage", return_value=0),
              patch.object(model.subprocess, "run", return_value=version),
              redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO())):
            ensure(model._build_locked(e, e.build_dir, log, []) == 1,
                   "native input drift must fail a build whose stages passed")
        record = json.loads(log.with_suffix(".json").read_text(encoding="utf-8"))
        ensure(record["exit_code"] == 1 and "header changed" in record["refusal"]
               and record["native_inputs"] is None,
               "the failed receipt must retain its native refusal")
        ensure(not (e.build_dir / model.native_build.STAMP).exists(),
               "failed native validation must publish no reuse stamp")


def _cmake_floor() -> None:
    with (patch.object(provision.shutil, "which", return_value="/fixture/cmake"),
          patch.object(provision, "_say", return_value="cmake version 2.8.12")):
        ensure(not provision._cmake().present, "an obsolete installed CMake must refuse")
    with (patch.object(provision.shutil, "which", return_value="/fixture/cmake"),
          patch.object(provision, "_say", return_value="cmake version 99.0.0")):
        ensure(provision._cmake().present, "a version satisfying the owning floor must pass")


def cases() -> list[Case]:
    return [Case("verified acquisition gates configuration", _acquisition_precedes_configuration),
            Case("offline environment and CLI selection", _offline_selection),
            Case("native input drift refuses complete build evidence", _native_refusal_is_not_success),
            Case("CMake provisioning reads the supported floor", _cmake_floor)]
