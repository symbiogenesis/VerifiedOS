# SPDX-License-Identifier: Apache-2.0
"""Dependency-reading refusals retain the admission CLI's named error boundary."""

import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import source_bindings
from vos.cli import admission


def _dependency_refusals() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-admission-dependencies-") as directory:
        root = Path(directory)
        package = root / "tools/vos"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        (root / "input.json").write_text("{}\n", encoding="utf-8")
        output = root / "result.json"
        sentinel = b"existing admission record\n"
        output.write_bytes(sentinel)
        args = ["production-record", "input.json", "--projections", "out/projections",
                "--build-record", "build.json", "--image", "image.elf", "--graph", "graph.json",
                "--out", "result.json"]
        for source, detail in (("from vos import missing_helper\n", "missing_helper"),
                               ("def incomplete(\n", "probe.py")):
            (package / "probe.py").write_text(source, encoding="utf-8")
            captured = StringIO()
            with (patch.dict(source_bindings.GROUPS, {"admission-production": ("tools/vos/probe.py",)}),
                  patch.object(admission.corpus, "find_root", return_value=root), redirect_stdout(captured)):
                code = admission.main(args)
            ensure(code == 2, "invalid dependency source must return the admission input-error status")
            diagnostic = captured.getvalue()
            ensure(diagnostic.startswith("FAIL admission:") and detail in diagnostic,
                   "dependency failures retain their named CLI diagnostic and source detail")
            ensure(output.read_bytes() == sentinel, "a dependency refusal must preserve the existing record")


def cases() -> list[Case]:
    return [Case("missing and malformed dependencies preserve CLI refusal behavior", _dependency_refusals)]
