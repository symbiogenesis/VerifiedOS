# SPDX-License-Identifier: Apache-2.0
"""Model reuse follows local producers and data rather than unrelated checkout edits."""

import json
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from tests.test_model_guards import _environment, _git, _pin
from vos import python_dependencies, receipts
from vos.cli import model

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def _fixture() -> Generator[Path]:
    implementation = python_dependencies.sources(ROOT, model.BUILD_ENTRYPOINTS)
    files = {name: (ROOT / name).read_text(encoding="utf-8") for name in implementation}
    files.update({
        "model/source.sail": "model bytes\n",
        "corpus/fixture.s": "fixture corpus bytes\n",
        "interfaces/block-device-contract.md": "fixture interface\n",
        "tools/generated/dialect-table.json": "fixture dialect table\n",
        model.sailbundle.BUNDLE: "fixture Sail bundle\n",
        model.sailbundle.SOURCE_IDENTITY: "fixture Sail source identity\n",
        "tools/pyproject.toml": "fixture Python requirements\n",
        "tools/uv.lock": "fixture Python lock\n",
        ".gitmodules": "fixture gitlink declarations\n",
        "tools/vos/vela/lsp.py": "unrelated editor implementation\n",
        "tools/vos/checks/links.py": "unrelated checker implementation\n",
        "tools/generated/proof-ledger.md": "unrelated proof ledger\n",
    })
    with sandbox_tree(files) as root:
        _pin(root, model.ORACLE_SRC, "1" * 40)
        _git(root, "commit", "-qm", "fixture model producers")
        yield root


def _unrelated_commits_reuse_the_build() -> None:
    with _fixture() as root:
        e = _environment(root)
        with (patch.object(receipts, "executables", return_value={"sail": "compiler bytes"}),
              patch.object(model, "_generator_identity", return_value={"fixture": True}),
              patch.object(model, "build_artifacts", return_value={}),
              patch.object(model.native_build, "verify")):
            before = model.build_identity(e)
            inputs = cast("dict[str, str]", before["inputs"])
            ensure("tools/vos/jsonc.py" in inputs and "tools/vos/python_dependencies.py" in inputs,
                   "the actual transitive parser and discovery implementation must be bound")
            e.log_dir.mkdir()
            log = e.log("model-build")
            log.write_text("fixture successful log\n", encoding="utf-8")
            revision = model._observed_revision(e)
            record = {"schema": 1, "exit_code": 0,
                      "stages": {"configure": 0, "build": 0, "ctest": 0},
                      "identity": before, "artifacts": {}, "observed_revision": revision,
                      "log_sha256": receipts.digest(log)}
            receipts.write(log.with_suffix(".json"), record)
            unrelated = ("tools/vos/vela/lsp.py", "tools/vos/checks/links.py",
                         "tools/generated/proof-ledger.md")
            for name in unrelated:
                ensure(name not in inputs, f"unrelated input entered the model closure: {name}")
                (root / name).write_text("changed unrelated bytes\n", encoding="utf-8")
            ensure(model.verified_build(e) == record, "unrelated edits must preserve build reuse")
            _git(root, "add", "--", *unrelated)
            _git(root, "commit", "-qm", "unrelated editor checker and ledger changes")
            ensure(model._observed_revision(e) != revision, "fixture commit must move provenance")
            ensure(model.verified_build(e) == record,
                   "unrelated commits must reuse the old build with its original truthful provenance")
            ensure(json.loads(log.with_suffix(".json").read_bytes())["observed_revision"] == revision,
                   "reuse must never rewrite the observed build revision")


def _relevant_changes_invalidate() -> None:
    with _fixture() as root:
        e = _environment(root)
        with (patch.object(receipts, "executables", return_value={"sail": "compiler bytes"}),
              patch.object(model, "_generator_identity", return_value={"fixture": True})):
            before = model.build_identity(e)
            for name in ("tools/vos/jsonc.py", "model/source.sail", "corpus/fixture.s",
                         "interfaces/block-device-contract.md", "tools/generated/dialect-table.json",
                         model.sailbundle.BUNDLE, model.sailbundle.SOURCE_IDENTITY,
                         "tools/pyproject.toml", "tools/uv.lock"):
                path = root / name
                original = path.read_bytes()
                path.write_bytes(original + b"\n# changed input\n")
                ensure(model.build_identity(e) != before, f"changed consumed input stayed fresh: {name}")
                path.write_bytes(original)
            with patch.object(receipts, "executables", return_value={"sail": "changed compiler"}):
                ensure(model.build_identity(e) != before, "changed compiler must invalidate")
            e.compilers.append("-DCMAKE_C_COMPILER=another-compiler")
            ensure(model.build_identity(e) != before, "changed configure options must invalidate")


def _new_imports_are_bound() -> None:
    with _fixture() as root:
        original = model.build_inputs(root)
        module = root / "tools/vos/jsonc.py"
        module.write_bytes(module.read_bytes() + b"\nfrom vos import dependency_fixture\n")
        helper = root / "tools/vos/dependency_fixture.py"
        helper.write_text("value = 1\n", encoding="utf-8")
        changed = model.build_inputs(root)
        ensure("tools/vos/dependency_fixture.py" not in original
               and "tools/vos/dependency_fixture.py" in changed,
               "a newly imported helper must join the current checkout manifest")
        helper.unlink()
        try:
            model.build_inputs(root)
        except ValueError as error:
            ensure("dependency_fixture" in str(error), "missing helper refusal must name its module")
        else:
            raise AssertionError("a missing imported model helper was omitted from identity")
        helper.write_text("value = 1\n", encoding="utf-8")
        (root / ".gitignore").write_text("tools/vos/dependency_fixture.py\n", encoding="utf-8")
        try:
            model.build_inputs(root)
        except ValueError as error:
            ensure("implementation inputs are not recorded" in str(error),
                   "ignored helper refusal must name the missing manifest boundary")
        else:
            raise AssertionError("a Git-ignored imported helper disappeared from model identity")
        _git(root, "add", "-f", "--", "tools/vos/dependency_fixture.py")
        ensure("tools/vos/dependency_fixture.py" in model.build_inputs(root),
               "an indexed helper stays bound even when an ignore rule matches it")


def cases() -> list[Case]:
    return [Case("unrelated edits and commits retain successful build reuse", _unrelated_commits_reuse_the_build),
            Case("consumed sources data locks tools and options invalidate", _relevant_changes_invalidate),
            Case("new import edges bind helpers and missing helpers refuse", _new_imports_are_bound)]
