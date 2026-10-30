# SPDX-License-Identifier: Apache-2.0
"""Selected proof staging keeps dependency order and refuses changed inputs."""

import tempfile
from collections.abc import Callable
from pathlib import Path

from tests.harness import Case, ensure
from vos import proof_staging


def _write(root: Path, name: str, text: str) -> Path:
    source = root / "proofs" / name
    source.parent.mkdir(exist_ok=True)
    source.write_bytes(text.encode("utf-8"))
    return source


def _refused(action: Callable[[], object], message: str) -> None:
    try:
        action()
    except proof_staging.StagingError as error:
        ensure(message in str(error), f"unexpected staging refusal: {error}")
        return
    raise AssertionError(f"expected staging refusal: {message}")


def _closure_and_order() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        shared = _write(root, "Shared.v", "Definition value := 1.\r\n")
        _write(root, "Left.v", "Require Shared.\n")
        _write(root, "Right.v", "Require Import Shared.\n")
        _write(root, "Root.v", "From Stdlib Require Import List.\nRequire Left Right.\n")
        _write(root, "Unrelated.v", "Definition other := 2.\n")
        staged = proof_staging.stage(root, root / "stage", ("Root.v", "Left.v"))
        ensure([source.name for source in staged.sources] ==
               ["Shared.v", "Left.v", "Right.v", "Root.v"], "closure compile order")
        ensure(staged.sources[0].read_bytes() == shared.read_bytes(), "staging changed CRLF bytes")
        ensure(staged.inputs == proof_staging.inputs(root, ("Root.v", "Left.v")),
               "read-only and staged source identities disagree")
        copied = staged.inputs
        copied.clear()
        ensure(len(staged.inputs) == 4, "caller changed retained staging identities")
        staged.validate(root)


def _entry_refusals() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        _write(root, "Root.v", "Definition value := 1.\n")
        for entries, message in (((), "nonempty"), (("Root.v", "Root.v"), "distinct"),
                                 (("Missing.v",), "unknown"), (("../Root.v",), "plain")):
            _refused(lambda entries=entries: proof_staging.inputs(root, entries), message)
        _refused(lambda: proof_staging.stage(root, root / "proofs", ("Root.v",)),
                 "overwrite the source")


def _cycles() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        _write(root, "Left.v", "Require Right.\n")
        _write(root, "Right.v", "Require Left.\n")
        _refused(lambda: proof_staging.stage(root, root / "stage", ("Left.v",)), "cycle")


def _changed_sources() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        _write(root, "Shared.v", "Definition value := 1.\n")
        _write(root, "Root.v", "Require Shared.\n")
        staged = proof_staging.stage(root, root / "stage", ("Root.v",))
        _write(root, "Shared.v", "Definition value := 2.\n")
        _refused(lambda: staged.validate(root), "source bytes changed")


def _changed_stage() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        _write(root, "Root.v", "Definition value := 1.\n")
        staged = proof_staging.stage(root, root / "stage", ("Root.v",))
        staged.sources[0].write_text("Definition value := 2.\n", encoding="utf-8")
        _refused(lambda: staged.validate(root), "staged proof bytes changed")


def _changed_closure() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        _write(root, "Extra.v", "Definition value := 1.\n")
        _write(root, "Root.v", "Definition value := 1.\n")
        staged = proof_staging.stage(root, root / "stage", ("Root.v",))
        _write(root, "Root.v", "Require Extra.\n")
        _refused(lambda: staged.validate(root), "dependency closure changed")


def cases() -> list[Case]:
    return [Case("closure-order-shared-input", _closure_and_order),
            Case("entry-refusals", _entry_refusals), Case("cycles", _cycles),
            Case("changed-source", _changed_sources), Case("changed-stage", _changed_stage),
            Case("changed-closure", _changed_closure)]
