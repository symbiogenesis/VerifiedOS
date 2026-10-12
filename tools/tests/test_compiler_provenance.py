# SPDX-License-Identifier: Apache-2.0
"""Native tool identities must match a contained build's recorded released lock."""

import copy
import json
import tempfile
from pathlib import Path

from tests import compiler_fixture
from tests.harness import Case, ensure
from vos import compiler_provenance as provenance


def locked_identities() -> None:
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        compiler = compiler_fixture.create(root)
        lock = root / provenance.LOCK
        result, files = provenance.read(compiler, lock)
        ensure(result["source_count"] == 1 and result["build_receipt"] == "present",
               "complete locked compiler refused")
        ensure(provenance.unchanged(files), "unchanged receipt refused")
        path = compiler.parent / "build-result.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        for role in provenance.TOOLS:
            for field, replacement in ((None, None), ("version", "0"),
                    ("reported_version", "version 9.3.01"), ("executable_sha256", "")):
                changed = copy.deepcopy(original)
                if field is None:
                    del changed["toolchain"][role]
                else:
                    changed["toolchain"][role][field] = replacement
                path.write_text(json.dumps(changed), encoding="utf-8")
                try:
                    provenance.read(compiler, lock)
                except ValueError:
                    continue
                raise AssertionError(f"{role} missing or changed {field} was accepted")
        path.write_text(json.dumps(original), encoding="utf-8")
        lock.write_text(lock.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
        ensure(not provenance.unchanged(files), "changed lock retained old identities")
        try:
            provenance.read(compiler, lock)
        except ValueError:
            return
        raise AssertionError("receipt with changed lock accepted")


def absent_is_explicit() -> None:
    with tempfile.TemporaryDirectory() as name:
        compiler = Path(name) / "ccomp"
        compiler.write_bytes(b"stock")
        result, files = provenance.read(compiler, required=False)
        ensure(result == {"build_receipt": "absent", "toolchain": None} and not files,
               "absent receipt was silently treated as a locked build")
        (compiler.parent / "build-result.json").write_text("{}", encoding="utf-8")
        try:
            provenance.read(compiler, required=False)
        except OSError:
            return
        raise AssertionError("partial receipt was hidden as absence")


def historical_inspection_never_accepts_a_target() -> None:
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        compiler = compiler_fixture.create(root)
        lock = root / provenance.LOCK
        current, _ = provenance.read(compiler, lock)
        old = {key: current[key] for key in ("revision", "kind", "compiler_sha256", "source_count")}
        old["kind"] = "fixture source build"
        ensure(provenance.inspect(old, lock) ==
               "historical incomplete compiler provenance; target acceptance unavailable",
               "historical inspection concealed unavailable target acceptance")
        ensure(provenance.inspect(current, lock) == "complete compiler provenance",
               "complete provenance was misclassified as historical")
        for raw in [old, {**old, "build_receipt": "present"}, {**old, "toolchain": None},
                    {**old, "source_count": True}, {**old, "source_count": 0},
                    {**old, "compiler_sha256": "invalid"}, {**old, "kind": ""}]:
            try:
                provenance.portable(raw, lock)
            except ValueError:
                pass
            else:
                raise AssertionError(f"incomplete or malformed producer accepted for target: {raw}")
            if raw == old:
                continue
            try:
                provenance.inspect(raw, lock)
            except ValueError:
                continue
            raise AssertionError(f"partial or malformed receipt hidden as historical: {raw}")


def cases() -> list[Case]:
    return [Case("complete native tool identities and missing/mismatched refusals", locked_identities),
            Case("receipt absence differs from invalid or partial receipt", absent_is_explicit),
            Case("historical inspection supplies no target acceptance",
                 historical_inspection_never_accepts_a_target)]
