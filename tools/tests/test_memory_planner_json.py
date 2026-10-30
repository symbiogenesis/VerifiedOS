# SPDX-License-Identifier: Apache-2.0
"""Planner reader policy and the certificate command's import boundary."""

import hashlib
import math
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import memory_planner_certificates as certificates
from vos.cli import memory_planner, memory_planner_certificates


def _reader_policy() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "input.json"
        for reader in (memory_planner.read_json, memory_planner_certificates.read_json):
            path.write_bytes(b'{"z": null, "a": [{"y": false, "x": 0}]}')
            inputs: dict[str, str] = {}
            decoded = reader(path, inputs)
            ensure(isinstance(decoded, dict) and list(decoded) == ["z", "a"],
                   "planner reader lost ordered members")
            ensure(decoded == {"z": None, "a": [{"y": False, "x": 0}]},
                   "planner reader changed nested values")
            ensure(inputs == {str(path): hashlib.sha256(path.read_bytes()).hexdigest()},
                   "planner reader no longer identifies the exact parsed bytes")
            for raw in (b'{"a": 0, "a": 1}', b'{"outer": [{"a": 0, "a": 1}]}',
                        br'{"a": 0, "\u0061": 1}'):
                path.write_bytes(raw)
                inputs = {}
                try:
                    reader(path, inputs)
                except ValueError as error:
                    ensure(type(error) is ValueError and str(error) == "duplicate JSON field: a",
                           "duplicate-field exception or diagnostic changed")
                else:
                    raise AssertionError("planner reader accepted a repeated decoded field")
                ensure(inputs == {str(path): hashlib.sha256(raw).hexdigest()},
                       "duplicate refusal lost the parsed input's fingerprint")


def _numeric_policies() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "number.json"
        for raw, diagnostic in ((b'1e999', "nonfinite JSON number"),
                                (b'NaN', "nonfinite JSON number: NaN"),
                                (b'Infinity', "nonfinite JSON number: Infinity")):
            path.write_bytes(raw)
            value = memory_planner.read_json(path, {})
            ensure(isinstance(value, float) and not math.isfinite(value),
                   "the planner reader's numeric policy changed")
            inputs: dict[str, str] = {}
            try:
                memory_planner_certificates.read_json(path, inputs)
            except certificates.CertificateError as error:
                ensure(str(error) == diagnostic, "certificate numeric diagnostic changed")
            else:
                raise AssertionError("certificate reader accepted a nonfinite number")
            ensure(inputs == {str(path): hashlib.sha256(raw).hexdigest()},
                   "numeric refusal lost its input fingerprint")
        path.write_bytes(b'{"integer": 2, "fraction": 0.25}')
        ensure(memory_planner_certificates.read_json(path, {}) == {"integer": 2, "fraction": 0.25},
               "certificate reader refused ordinary finite numbers")


def _certificate_import_boundary() -> None:
    done = subprocess.run(
        [sys.executable, "-c",
         "import sys; import vos.cli.memory_planner_certificates; "
         "print('vos.cli.memory_planner' in sys.modules); "
         "print('vos.memory_planner_adapters' in sys.modules)"],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
        check=False, timeout=30)
    ensure(done.returncode == 0, f"fresh certificate command import failed: {done.stderr}")
    ensure(done.stdout.splitlines() == ["False", "False"],
           "certificate command imported the planner command or its adapter tree")


def cases() -> list[Case]:
    return [Case("ordered readers and duplicate diagnostics", _reader_policy),
            Case("reader-specific numeric policies", _numeric_policies),
            Case("certificate command import boundary", _certificate_import_boundary)]
